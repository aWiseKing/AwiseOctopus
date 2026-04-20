import time
import os
from openai import OpenAI

class OpenAISandbox:
    """
    A Python sandbox execution environment based on OpenAI's Code Interpreter.
    It creates an Assistant with the `code_interpreter` tool to run code in an isolated container.
    """

    def __init__(self, api_key=None, base_url=None, model=None):
        # 尝试从环境变量获取配置，如果未提供参数
        api_key = api_key or os.environ.get("OPENAI_API_KEY") or os.environ.get("api_key")
        base_url = base_url or os.environ.get("OPENAI_BASE_URL") or os.environ.get("base_url")
        self.model = model or os.environ.get("MODEL") or "gpt-4o"
        
        self.client = OpenAI(api_key=api_key, base_url=base_url)
        self.assistant = self._create_assistant()
        # 默认创建一个持久的 Thread 以保持执行上下文
        self.thread = self.client.beta.threads.create()

    def _create_assistant(self):
        instructions = (
            "You are a strict Python Sandbox execution engine. "
            "You MUST execute the provided Python code using the `code_interpreter` tool. "
            "Return ONLY the exact console output (stdout and stderr) of the execution. "
            "Do NOT include any conversational text, markdown formatting, or explanations. "
            "If the code results in an error, return the exact error message."
        )
        return self.client.beta.assistants.create(
            name="Python Sandbox",
            instructions=instructions,
            model=self.model,
            tools=[{"type": "code_interpreter"}]
        )

    def execute_code(self, code: str) -> str:
        """
        Executes the provided Python code in the OpenAI Code Interpreter sandbox.
        """
        prompt = (
            "Execute the following python code using the code_interpreter tool and return ONLY the raw output or error:\n\n"
            f"```python\n{code}\n```"
        )
        
        # 将用户的代码发送到线程中
        self.client.beta.threads.messages.create(
            thread_id=self.thread.id,
            role="user",
            content=prompt
        )

        # 启动执行
        run = self.client.beta.threads.runs.create(
            thread_id=self.thread.id,
            assistant_id=self.assistant.id
        )

        # 轮询状态
        while run.status in ['queued', 'in_progress', 'cancelling']:
            time.sleep(1)
            run = self.client.beta.threads.runs.retrieve(
                thread_id=self.thread.id,
                run_id=run.id
            )

        if run.status == 'completed':
            messages = self.client.beta.threads.messages.list(
                thread_id=self.thread.id,
                order="desc"
            )
            # 获取最近一条由 assistant 回复的消息
            for msg in messages.data:
                if msg.role == 'assistant':
                    if hasattr(msg.content[0], 'text'):
                        content = msg.content[0].text.value
                        return content.strip()
            return "No output returned."
        elif run.status == 'failed':
            return f"Execution failed: {run.last_error.message if run.last_error else 'Unknown error'}"
        else:
            return f"Execution ended with status: {run.status}"

    def close(self):
        """
        Cleans up the Assistant and Thread to avoid unnecessary storage/costs.
        """
        try:
            self.client.beta.threads.delete(self.thread.id)
            self.client.beta.assistants.delete(self.assistant.id)
        except Exception as e:
            print(f"Error during cleanup: {e}")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
