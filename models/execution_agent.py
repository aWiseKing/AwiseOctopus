import json
from .tools import registry
from .experience_memory import ExperienceMemoryManager
from .experience_agent import ExperienceAgent
from .interaction import resolve_interaction_handler

class ExecutionAgent:
    def __init__(self, client, model, session_id=None, interaction_handler=None):
        self.client = client
        self.model = model
        self.session_id = session_id
        self.interaction_handler = resolve_interaction_handler(interaction_handler)
        self.memory_manager = ExperienceMemoryManager()
        self.experience_agent = ExperienceAgent(client, model)
        
        self.workspace = None
        if self.session_id:
            from .session_store import SessionStore
            store = SessionStore()
            self.workspace = store.get_workspace(self.session_id)
            store.close()
        if not self.workspace:
            from models.config_manager import ConfigManager
            self.workspace = ConfigManager().get("default_workspace")
            
        self.system_prompt = (
            "你是一个执行Agent（Worker）。你的任务是利用手头的技能工具，精准地完成思考Agent交给你的具体任务指令。\n"
            "遇到问题时，请自行分析并再次尝试。一旦你完成了任务，请直接用普通文本回答最终结果，不要返回额外的内容。\n"
            "如果没有合适的工具，你可以直接回答；如果有合适的工具，请务必使用工具。\n"
            "【特别注意】在执行直接操作宿主机PC的危险操作（如读写本地文件、修改系统设置）前，你必须先使用沙箱环境运行包含虚拟数据的测试代码，验证你的逻辑和语法。测试无误后，再执行真实的宿主机操作。"
        )
        
        if self.workspace:
            workspace_rule = (
                f"\n\n【工作区限制】\n当前设定的会话工作区是：{self.workspace}\n"
                "你的所有本地文件操作（包括读写、执行命令、代码生成等）都必须默认限制在此目录下进行。\n"
                "除非用户明确要求操作工作区外的特定文件，否则你的操作绝对不能超出该目录范围。"
            )
            self.system_prompt += workspace_rule

    def _append_tool_message(self, messages, tool_call_id, name, content) -> None:
        messages.append(
            {
                "role": "tool",
                "tool_call_id": tool_call_id,
                "name": name,
                "content": str(content),
            }
        )

    def run_stream(self, instruction):
        yield f"  >>> [执行Agent 启动] 接收到子任务: {instruction}"

        # 搜索历史经验
        hint = self.memory_manager.search_experience(
            "execution", instruction, session_id=self.session_id
        )

        messages = [{"role": "system", "content": self.system_prompt}]
        if hint:
            yield f"  >>> [执行Agent 经验记忆] 检索到相关历史经验，已注入上下文。"
            messages.append(
                {
                    "role": "system",
                    "content": (
                        "〖系统注入的历史经验（仅供参考，如与用户最新指令冲突，以用户指令为准）〗\n"
                        f"{hint}\n"
                        "〖经验参考结束〗"
                    ),
                }
            )

        messages.append({"role": "user", "content": instruction})

            
        process_log = []
        
        while True:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                tools=registry.schemas if registry.schemas else None
            )
            msg = response.choices[0].message
            
            if msg.tool_calls:
                messages.append(msg)
                for tool_call in msg.tool_calls:
                    name = getattr(tool_call.function, "name", None) or "unknown_tool"
                    try:
                        args = json.loads(tool_call.function.arguments)
                        yield f"    - [执行Agent 调用技能] {name}({args})"
                        
                        skill_info = registry.get_skill_info(name)
                        if skill_info and skill_info.get("requires_confirmation"):
                            from .safety_checker import is_action_safe
                            yield f"    - [执行Agent 安全审查] 正在分析 {name} 操作安全性..."
                            is_safe = is_action_safe(self.client, self.model, name, args)
                            
                            if is_safe:
                                yield f"    - [执行Agent 安全审查] LLM 判定该操作安全，已自动放行。"
                                result = registry.execute(name, args)
                            else:
                                if self.interaction_handler:
                                    yield f"    - [执行Agent 暂停] 发现高危操作，等待用户确认 {name}..."
                                    user_reply = self.interaction_handler(name, args)
                                    if str(user_reply).strip().lower() in ['y', 'yes', '允许', 'ok']:
                                        result = registry.execute(name, args)
                                    else:
                                        result = f"用户拒绝了该操作，用户的建议/原因是: {user_reply}"
                                else:
                                    yield f"    - [执行Agent 警告] 高危操作 {name} 需要用户确认，但未配置交互处理器，默认拒绝执行。"
                                    result = "操作被拒绝：未配置用户确认交互机制。"
                        else:
                            result = registry.execute(name, args)
                        
                        yield f"    - [执行Agent 技能返回结果] {result}"
                        process_log.append(f"Call {name}({args}) -> Result: {result}")
                        self._append_tool_message(messages, tool_call.id, name, result)
                    except Exception as e:
                        error_text = f"Tool call failed: {type(e).__name__}: {e}"
                        yield f"    - [执行Agent 技能调用失败] {name}: {type(e).__name__}: {e}"
                        process_log.append(f"Call {name} failed -> {error_text}")
                        self._append_tool_message(messages, tool_call.id, name, error_text)
            else:
                final_result = msg.content
                yield f"  <<< [执行Agent 完成] 结果反馈: {final_result}"
                
                # 记录经验
                yield f"  >>> [执行Agent] 开始请求经验总结 Agent 处理执行结果..."
                process_log_str = "\n".join(process_log)
                for log_msg in self.experience_agent.process_experience_stream(
                    "execution",
                    instruction,
                    process_log_str,
                    final_result,
                    session_id=self.session_id,
                ):
                    yield f"      {log_msg}"
                
                return final_result

    def run(self, instruction):
        gen = self.run_stream(instruction)
        try:
            while True:
                log_msg = next(gen)
                print(log_msg)
        except StopIteration as e:
            return e.value

    async def async_run(self, instruction):
        """异步执行封装，通过 asyncio.to_thread 在线程池中执行同步的 run_stream"""
        import asyncio
        return await asyncio.to_thread(self.run, instruction)
