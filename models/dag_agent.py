import json
import jsonschema
from .tools import registry

def _validate_dag_tasks(tasks, schema):
    """
    校验 DAG 任务列表的 Schema 结构以及逻辑（存在性和无环检测）
    返回 (is_valid, error_message)
    """
    # 1. 基础 Schema 校验
    try:
        # tasks 在外部是 list，但 schema 是为包裹 tasks 的 object 设计的
        # 所以我们包装一下进行校验
        jsonschema.validate(instance={"tasks": tasks}, schema=schema)
    except jsonschema.exceptions.ValidationError as e:
        return False, f"Schema validation error: {e.message}"

    # 2. 逻辑校验：提取所有的 task_id
    task_ids = set()
    for t in tasks:
        if t['id'] in task_ids:
            return False, f"Logical error: Duplicate task id '{t['id']}' found."
        task_ids.add(t['id'])

    # 3. 逻辑校验：依赖是否存在
    for t in tasks:
        for dep in t.get('dependencies', []):
            if dep not in task_ids:
                return False, f"Logical error: Task '{t['id']}' depends on non-existent task '{dep}'."

    # 4. 逻辑校验：循环依赖检测 (DFS 拓扑排序)
    # 状态: 0=未访问, 1=访问中, 2=已访问
    visited = {tid: 0 for tid in task_ids}
    adj_list = {t['id']: t.get('dependencies', []) for t in tasks}

    def has_cycle(tid):
        if visited[tid] == 1:
            return True
        if visited[tid] == 2:
            return False
        
        visited[tid] = 1
        for dep in adj_list[tid]:
            if has_cycle(dep):
                return True
        visited[tid] = 2
        return False

    for tid in task_ids:
        if visited[tid] == 0:
            if has_cycle(tid):
                return False, f"Logical error: Circular dependency detected involving task '{tid}'."

    # 5. 逻辑校验：类型校验
    for t in tasks:
        t_type = t.get('type', 'agent')
        if t_type == 'tool':
            if 'tool' not in t or 'input' not in t:
                return False, f"Logical error: Task '{t['id']}' with type 'tool' must have 'tool' and 'input' fields."
        else:
            if 'instruction' not in t:
                return False, f"Logical error: Task '{t['id']}' with type 'agent' must have 'instruction' field."

    return True, None


class DAGAgent:
    def __init__(self, client, model):
        self.client = client
        self.model = model
        
        execution_tools_info = json.dumps(registry.schemas, ensure_ascii=False)
        self.system_prompt = (
            "你是一个专业的 DAG（有向无环图）任务架构师（DAG Agent）。\n"
            "你的任务是将思考Agent（ThinkingAgent）传给你的【任务执行计划】转化为符合规范的 DAG 任务 JSON 数组。\n"
            "在 DAG 图中，你需要将任务进行**细致的拆分**，支持两种任务节点类型：\n"
            "  1. `type='tool'`：直接调用特定的执行工具。必须指定 `tool`（工具名称）和 `input`（工具参数）。\n"
            "  2. `type='agent'`：将复杂的模糊指令委派给执行Agent处理。必须指定 `instruction`。\n"
            "请优先将明确的操作拆分为 `type='tool'` 节点。当前可直接调用的执行工具（用于 type='tool'）如下：\n"
            f"{execution_tools_info}\n"
            "\n**【动态DAG调整（复盘机制）】**\n"
            "如果思考Agent的计划中提到某任务执行后可能需要根据它的结果来决定后续任务如何进行，请将该任务的 `requires_review` 设为 true。\n"
            "你必须调用 `create_task` 工具来输出最终的 DAG 图。\n"
            "如果收到校验失败的反馈，你必须仔细检查错误信息并修复 DAG 的结构异常，重新调用 `create_task`。\n"
        )
        
        self.tools_schema = [
            {
                "type": "function",
                "function": {
                    "name": "create_task",
                    "description": "输出一个基于 DAG（有向无环图）的任务计划。",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "tasks": {
                                "type": "array",
                                "description": "DAG任务列表，每个任务包含id、指令和依赖项。",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "id": {
                                            "type": "string",
                                            "description": "任务的唯一标识符，例如 'task_1'"
                                        },
                                        "type": {
                                            "type": "string",
                                            "enum": ["tool", "agent"],
                                            "description": "任务类型。'tool'表示直接调用具体的工具，'agent'表示委派给执行Agent处理复杂逻辑"
                                        },
                                        "tool": {
                                            "type": "string",
                                            "description": "如果type为'tool'，指定要调用的工具名称"
                                        },
                                        "input": {
                                            "type": "object",
                                            "description": "如果type为'tool'，指定工具的输入参数"
                                        },
                                        "instruction": {
                                            "type": "string",
                                            "description": "如果type为'agent'，给出执行指令，给执行Agent看"
                                        },
                                        "dependencies": {
                                            "type": "array",
                                            "items": {"type": "string"},
                                            "description": "该任务依赖的其他任务id列表。如果是独立任务，传空数组 []"
                                        },
                                        "requires_review": {
                                            "type": "boolean",
                                            "description": "是否需要在该任务完成后暂停执行，并将结果交由思考Agent进行复盘。如果其结果可能改变后续走向，设为true。"
                                        }
                                    },
                                    "required": ["id", "type", "dependencies"]
                                }
                            }
                        },
                        "required": ["tasks"]
                    }
                }
            }
        ]

    def _append_tool_message(self, messages, tool_call_id, name, content) -> None:
        messages.append(
            {
                "role": "tool",
                "tool_call_id": tool_call_id,
                "name": name,
                "content": str(content),
            }
        )

    def generate_dag_stream(self, plan):
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": f"请将以下任务计划转化为 DAG 图：\n\n{plan}"}
        ]
        yield ("RUNNING", "\n=== [DAG Agent 启动] 开始转化为 DAG 任务图 ===")
        
        while True:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                tools=self.tools_schema,
                tool_choice="auto",
            )
            msg = response.choices[0].message
            messages.append(msg)
            
            if msg.tool_calls:
                for tool_call in msg.tool_calls:
                    name = getattr(tool_call.function, "name", None) or "unknown_tool"
                    try:
                        args = json.loads(tool_call.function.arguments)
                        
                        if name == "create_task":
                            tasks = args.get("tasks", [])
                            create_task_schema = next((t["function"]["parameters"] for t in self.tools_schema if t["function"]["name"] == "create_task"), None)
                            
                            is_valid, error_msg = _validate_dag_tasks(tasks, create_task_schema)
                            if not is_valid:
                                yield ("RUNNING", f"\n[DAG Agent 校验失败] DAG图存在错误: {error_msg}")
                                self._append_tool_message(
                                    messages,
                                    tool_call.id,
                                    name,
                                    f"Failed to create task due to validation error: {error_msg}. 你必须修复这个 DAG 图的异常并重新调用 `create_task`。",
                                )
                                continue
                                
                            yield ("RUNNING", f"\n=== [DAG Agent 转换完成] 输出DAG任务图: 共 {len(tasks)} 个任务 ===")
                            dag_json = json.dumps(tasks, ensure_ascii=False, indent=2)
                            yield ("RUNNING", f"\n[DAG 任务图详情]:\n{dag_json}")
                            
                            yield ("FINISHED", tasks)
                            return tasks
                        else:
                            yield ("RUNNING", f"\n[DAG Agent 错误] 调用了未知工具: {name}")
                            self._append_tool_message(
                                messages,
                                tool_call.id,
                                name,
                                f"Error: Unknown tool '{name}'.",
                            )
                    except Exception as e:
                        yield ("RUNNING", f"\n[DAG Agent 工具调用失败] {name}: {type(e).__name__}: {e}")
                        self._append_tool_message(
                            messages,
                            tool_call.id,
                            name,
                            f"Tool call failed: {type(e).__name__}: {e}",
                        )
            else:
                if msg.content:
                    yield ("RUNNING", f"\n[DAG Agent 自言自语] {msg.content}")
                    messages.append({"role": "user", "content": "请调用 create_task 工具输出 DAG 图。"})
