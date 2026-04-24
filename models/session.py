import uuid
from .thinking_agent import ThinkingAgent
from .dag_executor import DAGExecutor
from .interaction import resolve_interaction_handler

class Session:
    """
    Session 类负责封装一个完整的 Agent 对话上下文，
    协调 ThinkingAgent 的思考规划、DAGExecutor 的异步执行，以及最终的结果总结。
    """
    def __init__(self, client, model, session_id=None, interaction_handler=None):
        self.session_id = session_id or str(uuid.uuid4())
        self.client = client
        self.model = model
        self.interaction_handler = resolve_interaction_handler(interaction_handler)
        self.agent = ThinkingAgent(client, model, interaction_handler=self.interaction_handler)
        
    def think_stream(self, prompt):
        """流式生成思考过程"""
        return self.agent.run_stream(prompt)
        
    def think(self, prompt):
        """阻塞生成思考结果"""
        return self.agent.run(prompt)
        
    async def execute_dag_async(self, tasks, on_status_change=None, interaction_handler=None):
        """异步执行 DAG 任务图"""
        effective_handler = interaction_handler if interaction_handler is not None else self.interaction_handler
        executor = DAGExecutor(
            tasks=tasks,
            client=self.client,
            model=self.model,
            thinking_agent=self.agent,
            on_status_change=on_status_change,
            interaction_handler=effective_handler
        )
        return await executor.execute()
        
    def summarize_stream(self, prompt, results):
        """流式生成 DAG 执行结果的总结"""
        return self.agent.summarize_dag_results_stream(prompt, results)
        
    @property
    def messages(self):
        """获取当前会话的历史消息"""
        return self.agent.messages
