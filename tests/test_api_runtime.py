import asyncio
import tempfile
import unittest

from models.agent_errors import AgentOperationAbortedError
from models.api_runtime import AgentApiRuntime, encode_ndjson
from models.memory import MemoryManager
from models.session_store import SessionStore


class FakeSession:
    def __init__(self, client, model, session_id=None, interaction_handler=None):
        self.session_id = session_id
        self.interaction_handler = interaction_handler

    def think_stream(self, prompt):
        if prompt == "ask":
            yield "RUNNING", "start ask"
            reply = yield "ASK_USER", "need input"
            yield "RUNNING", f"got {reply}"
            yield "FINISHED", "done after ask"
            return
        if prompt == "dag":
            yield "RUNNING", "planning dag"
            yield "FINISHED", [
                {"id": "task-1", "instruction": "do work", "dependencies": []}
            ]
            return
        if prompt == "approval":
            yield "RUNNING", "planning approval dag"
            yield "FINISHED", [
                {"id": "approval-task", "instruction": "danger", "dependencies": []}
            ]
            return
        if prompt == "dag-abort":
            yield "RUNNING", "planning abort dag"
            yield "FINISHED", [
                {"id": "abort-task", "instruction": "abort work", "dependencies": []}
            ]
            return
        if prompt == "summary-abort":
            yield "RUNNING", "planning summary abort dag"
            yield "FINISHED", [
                {"id": "summary-task", "instruction": "summary work", "dependencies": []}
            ]
            return
        if prompt == "abort":
            yield "RUNNING", "before abort"
            raise AgentOperationAbortedError(
                "思考阶段 调用模型服务失败：请求频率超限或额度已耗尽。Agent 操作已中止，请回到对话框后重试，或调整模型/配额后继续。",
                code="llm_rate_limited",
            )
        if prompt == "boom":
            yield "RUNNING", "before boom"
            raise RuntimeError("boom")
        yield "RUNNING", "simple log"
        yield "FINISHED", "simple answer"

    async def execute_dag_async(self, tasks, on_status_change=None, interaction_handler=None):
        if on_status_change:
            on_status_change(
                {
                    "pending": [task["id"] for task in tasks],
                    "running": [],
                    "completed": [],
                    "tasks": {task["id"]: task for task in tasks},
                }
            )
        task_id = tasks[0]["id"]
        if task_id == "approval-task":
            decision = await asyncio.to_thread(
                interaction_handler,
                "shell_command",
                {"command": "Remove-Item demo.txt"},
            )
            return {"approval-task": decision.decision}
        if task_id == "abort-task":
            raise AgentOperationAbortedError(
                "执行阶段 调用模型服务失败：请求频率超限或额度已耗尽。Agent 操作已中止，请回到对话框后重试，或调整模型/配额后继续。",
                code="llm_rate_limited",
            )
        if task_id == "summary-task":
            return {"summary-task": "ok"}
        return {"task-1": "ok"}

    def summarize_stream(self, prompt, results):
        if prompt == "summary-abort":
            raise AgentOperationAbortedError(
                "结果总结阶段 调用模型服务失败：请求频率超限或额度已耗尽。Agent 操作已中止，请回到对话框后重试，或调整模型/配额后继续。",
                code="llm_rate_limited",
            )
        yield "sum"
        yield "mary"


async def collect(stream):
    return [event async for event in stream]


class TestAgentApiRuntime(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.store = SessionStore(db_path=f"{self.tempdir.name}/session.db")
        self.memory_manager = MemoryManager(
            db_path=f"{self.tempdir.name}/experience.db",
            chroma_path=f"{self.tempdir.name}/vec",
        )
        self.runtime = AgentApiRuntime(
            store=self.store,
            session_factory=FakeSession,
            client_factory=lambda: object(),
            memory_manager=self.memory_manager,
            model="fake-model",
        )

    def tearDown(self):
        self.runtime.close()
        self.tempdir.cleanup()

    async def test_create_list_and_load_client_messages(self):
        created = await self.runtime.create_session()
        self.store.append_message(created["id"], {"role": "user", "content": "hello"})
        self.store.append_message(
            created["id"],
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [{"id": "call-1"}],
            },
        )
        self.store.append_message(created["id"], {"role": "assistant", "content": "hi"})

        sessions = await self.runtime.list_sessions()
        messages = await self.runtime.load_session_history(created["id"])

        self.assertEqual(sessions[0]["id"], created["id"])
        self.assertEqual(sessions[0]["preview"], "hi")
        self.assertEqual([message["content"] for message in messages], ["hello", "hi"])
        self.assertEqual(messages[0]["kind"], "text")
        self.assertEqual(messages[1]["kind"], "finalAnswer")

    async def test_memory_management_runtime_methods(self):
        memory_id = self.memory_manager.add_memory(
            mode="long_term",
            scope="user_preference",
            content="用户偏好中文。",
            summary="中文偏好",
            confidence=0.9,
            importance=0.9,
        )

        listed = await self.runtime.list_memories(mode="long", limit=10)
        shown = await self.runtime.get_memory(memory_id)
        deleted = await self.runtime.delete_memory(memory_id)

        self.assertEqual(listed[0]["id"], memory_id)
        self.assertEqual(shown["summary"], "中文偏好")
        self.assertEqual(deleted, {"deleted": True, "id": memory_id})

    async def test_send_prompt_simple_answer_flow(self):
        events = await collect(
            self.runtime.send_prompt_stream(session_id="s-simple", prompt="hello")
        )

        self.assertEqual(
            [event["type"] for event in events],
            ["thinking_log", "final_answer"],
        )
        self.assertEqual(events[-1]["text"], "simple answer")

    async def test_ask_user_pause_and_reply_resume(self):
        first_events = await collect(
            self.runtime.send_prompt_stream(session_id="s-ask", prompt="ask")
        )
        second_events = await collect(
            self.runtime.reply_to_ask_user_stream(session_id="s-ask", reply="details")
        )

        self.assertEqual(first_events[-1], {"type": "ask_user", "text": "need input"})
        self.assertEqual(
            [event["type"] for event in second_events],
            ["thinking_log", "final_answer"],
        )
        self.assertEqual(second_events[-1]["text"], "done after ask")

    async def test_dag_flow_outputs_contract_events(self):
        events = await collect(
            self.runtime.send_prompt_stream(session_id="s-dag", prompt="dag")
        )

        self.assertEqual(
            [event["type"] for event in events],
            [
                "thinking_log",
                "dag_planned",
                "dag_status",
                "dag_result",
                "summary_chunk",
                "summary_chunk",
                "final_answer",
            ],
        )
        self.assertEqual(events[-1]["text"], "summary")
        self.assertTrue(all(encode_ndjson(event).endswith("\n") for event in events))

    async def test_approval_pause_and_decision_resume(self):
        first_events = await collect(
            self.runtime.send_prompt_stream(session_id="s-approval", prompt="approval")
        )
        approval = first_events[-1]["approvalRequest"]

        self.assertEqual(first_events[-1]["type"], "approval_request")
        self.assertTrue(approval["is_delete_operation"])
        self.assertFalse(approval["session_choice_enabled"])

        second_events = await collect(
            self.runtime.approval_decision_stream(
                session_id="s-approval",
                decision="only",
            )
        )

        self.assertEqual(
            [event["type"] for event in second_events],
            ["dag_result", "summary_chunk", "summary_chunk", "final_answer"],
        )
        self.assertEqual(second_events[0]["rawPayload"], {"approval-task": "only"})

    async def test_exception_becomes_error_event(self):
        events = await collect(
            self.runtime.send_prompt_stream(session_id="s-boom", prompt="boom")
        )

        self.assertEqual(events[-1]["type"], "error")
        self.assertIn("RuntimeError: boom", events[-1]["text"])

    async def test_abort_error_becomes_fatal_error_event(self):
        events = await collect(
            self.runtime.send_prompt_stream(session_id="s-abort", prompt="abort")
        )

        self.assertEqual(events[-1]["type"], "error")
        self.assertTrue(events[-1]["fatal"])
        self.assertTrue(events[-1]["shouldReturnToChat"])
        self.assertEqual(events[-1]["errorCode"], "llm_rate_limited")
        self.assertIn("Agent 操作已中止", events[-1]["text"])

    async def test_dag_abort_becomes_fatal_error_event(self):
        events = await collect(
            self.runtime.send_prompt_stream(session_id="s-dag-abort", prompt="dag-abort")
        )

        self.assertEqual(
            [event["type"] for event in events],
            ["thinking_log", "dag_planned", "dag_status", "error"],
        )
        self.assertTrue(events[-1]["fatal"])
        self.assertTrue(events[-1]["shouldReturnToChat"])

    async def test_summary_abort_becomes_fatal_error_event(self):
        events = await collect(
            self.runtime.send_prompt_stream(
                session_id="s-summary-abort",
                prompt="summary-abort",
            )
        )

        self.assertEqual(
            [event["type"] for event in events],
            ["thinking_log", "dag_planned", "dag_status", "dag_result", "error"],
        )
        self.assertTrue(events[-1]["fatal"])
        self.assertEqual(events[-1]["errorCode"], "llm_rate_limited")


if __name__ == "__main__":
    unittest.main()
