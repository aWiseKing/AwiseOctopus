import json
from .tools import registry

class ExecutionAgent:
    def __init__(self, client, model):
        self.client = client
        self.model = model
        self.system_prompt = (
            "你是一个执行Agent（Worker）。你的任务是利用手头的技能工具，精准地完成思考Agent交给你的具体任务指令。\n"
            "遇到问题时，请自行分析并再次尝试。一旦你完成了任务，请直接用普通文本回答最终结果，不要返回额外的内容。\n"
            "如果没有合适的工具，你可以直接回答；如果有合适的工具，请务必使用工具。"
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
