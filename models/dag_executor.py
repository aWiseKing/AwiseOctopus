import asyncio
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.events import EVENT_JOB_EXECUTED, EVENT_JOB_ERROR
from .execution_agent import ExecutionAgent
from .interaction import resolve_interaction_handler
from .tool_runtime import prepare_tool_args, resolve_workspace_for_session

class DAGExecutor:
    def __init__(self, tasks, client, model, thinking_agent, on_status_change=None, interaction_handler=None):
        self.client = client
        self.model = model
        self.thinking_agent = thinking_agent
        self.on_status_change = on_status_change
        self.interaction_handler = resolve_interaction_handler(
            interaction_handler,
            session_id=getattr(thinking_agent, "session_id", None),
        )
        self.workspace = resolve_workspace_for_session(
            getattr(thinking_agent, "session_id", None)
        )
        
        # 记录所有的任务对象 {task_id: task_dict}
        self.all_tasks = {t['id']: t for t in tasks}
        # 待执行任务 id 集合
        self.pending_task_ids = set(self.all_tasks.keys())
        # 已完成任务 id 集合
        self.completed_task_ids = set()
        # 正在执行的任务 id 集合
        self.running_task_ids = set()
        
        # 记录任务执行结果 {task_id: result_string}
        self.task_results = {}
        
        # 调度器和全局锁
        self.scheduler = AsyncIOScheduler()
        self.is_reviewing = False
        
        # 用于等待所有任务完成的事件
        self.all_done_event = asyncio.Event()

    def _get_pending_tasks_list(self):
        """获取当前还未执行完毕的任务列表（用于传递给思考Agent）"""
        return [self.all_tasks[t] for t in self.pending_task_ids]

    def _notify_status(self):
        """触发状态更新回调"""
        if self.on_status_change:
            self.on_status_change({
                "pending": list(self.pending_task_ids),
                "running": list(self.running_task_ids),
                "completed": list(self.completed_task_ids),
                "tasks": self.all_tasks
            })

    async def _execute_task_wrapper(self, task_id, task_data):
        """包装 ExecutionAgent 或直接工具的执行，以便作为 apscheduler 的 job 运行"""
        task_type = task_data.get('type', 'agent')
        print(f"\n[DAG 执行器] 开始执行任务: {task_id} (类型: {task_type})")
        
        if task_type == 'tool':
            from .tools import registry
            tool_name = task_data.get('tool')
            tool_args = prepare_tool_args(
                tool_name,
                task_data.get('input', {}),
                workspace=self.workspace,
            )
            
            skill_info = registry.get_skill_info(tool_name)
            if skill_info and skill_info.get("requires_confirmation"):
                from .interaction import format_approval_status, format_rejection_message
                from .safety_checker import is_action_safe
                print(f"\n[DAG 执行器] 正在分析 {tool_name} 操作安全性...")
                is_safe = await asyncio.to_thread(is_action_safe, self.client, self.model, tool_name, tool_args)
                
                if is_safe:
                    print(f"\n[DAG 执行器] LLM 判定该操作安全，已自动放行。")
                    result = await asyncio.to_thread(registry.execute, tool_name, tool_args)
                else:
                    if self.interaction_handler:
                        print(f"\n[DAG 执行器] 发现高危操作，等待用户确认 {tool_name}...")
                        decision = await asyncio.to_thread(
                            self.interaction_handler, tool_name, tool_args
                        )
                        status_text = format_approval_status(decision, tool_name)
                        if status_text:
                            print(f"\n[DAG 执行器] {status_text}")
                        if decision.allow_current:
                            result = await asyncio.to_thread(registry.execute, tool_name, tool_args)
                        else:
                            result = format_rejection_message(decision)
                    else:
                        print(f"\n[DAG 执行器] 警告: 高危操作 {tool_name} 需要确认，但未配置交互机制，拒绝执行。")
                        result = "操作被拒绝：未配置用户确认交互机制。"
            else:
                result = await asyncio.to_thread(registry.execute, tool_name, tool_args)
        else:
            worker = ExecutionAgent(
                self.client,
                self.model,
                session_id=getattr(self.thinking_agent, "session_id", None),
                interaction_handler=self.interaction_handler,
            )
            result = await worker.async_run(task_data.get('instruction', ''))
            
        return {"task_id": task_id, "result": result}

    def _schedule_ready_tasks(self):
        """检查 pending_tasks，如果有依赖已全部满足的任务且当前不在复盘中，则加入调度"""
        if self.is_reviewing:
            return
            
        ready_tasks = []
        for task_id in list(self.pending_task_ids):
            if task_id in self.running_task_ids:
                continue
                
            task = self.all_tasks[task_id]
            deps = task.get("dependencies", [])
            # 检查所有依赖是否都在 completed_task_ids 中
            if all(dep in self.completed_task_ids for dep in deps):
                ready_tasks.append(task_id)
                
        for task_id in ready_tasks:
            self.running_task_ids.add(task_id)
            task = self.all_tasks[task_id]
            # 添加 job
            self.scheduler.add_job(
                self._execute_task_wrapper,
                kwargs={"task_id": task_id, "task_data": task},
                id=task_id
            )
            
        if ready_tasks:
            self._notify_status()

    async def _handle_review(self, completed_task_id, result):
        """异步处理任务复盘逻辑"""
        self.is_reviewing = True
        
        # 使用 to_thread 调用 ThinkingAgent 的复盘逻辑
        pending_list = self._get_pending_tasks_list()
        new_dag = await asyncio.to_thread(
            self.thinking_agent.review_dag, 
            completed_task_id, 
            result, 
            pending_list
        )
        
        if isinstance(new_dag, list):
            # 思考 Agent 返回了新的 DAG，局部覆盖
            print(f"\n[DAG 执行器] 接收到新的 DAG 计划，更新任务图...")
            
            # 只清除尚未运行的 pending_tasks
            for tid in list(self.pending_task_ids):
                if tid not in self.running_task_ids:
                    self.pending_task_ids.remove(tid)
            
            # 将新的 DAG 任务加入
            for task in new_dag:
                self.all_tasks[task['id']] = task
                self.pending_task_ids.add(task['id'])
            
            self._notify_status()
        else:
            print(f"\n[DAG 执行器] 思考Agent 决定维持原计划。")
            
        self.is_reviewing = False
        
        # 检查是否全部完成
        if not self.pending_task_ids:
            self.all_done_event.set()
        else:
            self._schedule_ready_tasks()

    def _job_listener(self, event):
        """监听 job 完成或出错事件"""
        if event.code == EVENT_JOB_ERROR:
            print(f"\n[DAG 执行器] 任务 {event.job_id} 执行出错: {event.exception}")
            # 暂时标记为完成以防阻塞，或者触发其他错误处理
            task_id = event.job_id
            result = f"Error: {event.exception}"
        else:
            # 正常完成
            retval = event.retval
            task_id = retval["task_id"]
            result = retval["result"]
            
        print(f"\n[DAG 执行器] 任务 {task_id} 执行完毕。")
        self.task_results[task_id] = result
        
        # 更新状态集合
        if task_id in self.running_task_ids:
            self.running_task_ids.remove(task_id)
        if task_id in self.pending_task_ids:
            self.pending_task_ids.remove(task_id)
        self.completed_task_ids.add(task_id)
        
        self._notify_status()
        
        task_info = self.all_tasks.get(task_id, {})
        requires_review = task_info.get("requires_review", False)
        
        if requires_review:
            # 启动异步任务进行 review
            asyncio.create_task(self._handle_review(task_id, result))
        else:
            # 正常继续调度
            if not self.pending_task_ids:
                self.all_done_event.set()
            else:
                self._schedule_ready_tasks()

    async def execute(self):
        """启动 DAG 执行"""
        print("\n=== [DAG 执行器] 开始动态执行任务图 ===")
        self.scheduler.add_listener(self._job_listener, EVENT_JOB_EXECUTED | EVENT_JOB_ERROR)
        self.scheduler.start()
        
        self._notify_status()
        
        if not self.pending_task_ids:
            return self.task_results
            
        self._schedule_ready_tasks()
        
        # 等待所有任务完成
        await self.all_done_event.wait()
        
        self.scheduler.shutdown()
        print("\n=== [DAG 执行器] 所有任务执行完毕 ===")
        return self.task_results
