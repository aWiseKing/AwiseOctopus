import json
from .tools import registry

class ExecutionAgent:
    def __init__(self, client, model, interaction_handler=None):
        self.client = client
        self.model = model
        self.interaction_handler = interaction_handler
        self.system_prompt = (
            "你是一个执行Agent（Worker）。你的任务是利用手头的技能工具，精准地完成思考Agent交给你的具体任务指令。\n"
            "遇到问题时，请自行分析并再次尝试。一旦你完成了任务，请直接用普通文本回答最终结果，不要返回额外的内容。\n"
            "如果没有合适的工具，你可以直接回答；如果有合适的工具，请务必使用工具。\n"
            "【特别注意】在执行直接操作宿主机PC的危险操作（如读写本地文件、修改系统设置）前，你必须先使用沙箱环境运行包含虚拟数据的测试代码，验证你的逻辑和语法。测试无误后，再执行真实的宿主机操作。"
        )

    def run_stream(self, instruction):
        yield f"  >>> [执行Agent 启动] 接收到子任务: {instruction}"
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": instruction}
        ]
        
        while True:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                tools=registry.schemas if registry.schemas else None
            )
            msg = response.choices[0].message
            messages.append(msg)
            
            if msg.tool_calls:
                for tool_call in msg.tool_calls:
                    name = tool_call.function.name
                    args = json.loads(tool_call.function.arguments)
                    yield f"    - [执行Agent 调用技能] {name}({args})"
                    
                    skill_info = registry.get_skill_info(name)
                    if skill_info and skill_info.get("requires_confirmation"):
                        if self.interaction_handler:
                            yield f"    - [执行Agent 暂停] 等待用户确认高危操作 {name}..."
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
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "name": name,
                        "content": str(result)
                    })
            else:
                final_result = msg.content
                yield f"  <<< [执行Agent 完成] 结果反馈: {final_result}"
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
