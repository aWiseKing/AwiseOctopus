from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

from models.dag_agent import DAGAgent
from models.execution_agent import ExecutionAgent
from models.thinking_agent import ThinkingAgent


def make_tool_call(call_id: str, name: str, arguments: str):
    return SimpleNamespace(
        id=call_id,
        type="function",
        function=SimpleNamespace(name=name, arguments=arguments),
    )


def make_message(*, content=None, tool_calls=None, reasoning_content=None):
    return SimpleNamespace(
        role="assistant",
        content=content,
        tool_calls=tool_calls,
        reasoning_content=reasoning_content,
    )


def make_response(message):
    return SimpleNamespace(choices=[SimpleNamespace(message=message)])


class FakeCompletions:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if not self.responses:
            raise AssertionError("No fake responses left.")
        return self.responses.pop(0)


class FakeClient:
    def __init__(self, responses):
        self.chat = SimpleNamespace(completions=FakeCompletions(responses))


class TestAgentToolCallSequence(unittest.TestCase):
    def test_thinking_agent_merges_injected_experience_into_single_system_message(self) -> None:
        client = FakeClient(
            [
                make_response(
                    make_message(
                        tool_calls=[
                            make_tool_call(
                                "call_finish",
                                "finish_task",
                                '{"final_answer":"ok"}',
                            )
                        ]
                    )
                )
            ]
        )
        agent = ThinkingAgent(client, "fake-model")

        with patch.object(
            agent.memory_manager, "search_experience", return_value="历史经验"
        ), patch.object(
            agent.experience_agent, "process_experience_stream", return_value=[]
        ):
            result = agent.run("hello")

        self.assertEqual(result, "ok")
        first_call_messages = client.chat.completions.calls[0]["messages"]
        system_messages = [
            msg for msg in first_call_messages if isinstance(msg, dict) and msg.get("role") == "system"
        ]
        self.assertEqual(len(system_messages), 1)
        self.assertIn("历史经验", system_messages[0].get("content", ""))

    def test_thinking_agent_appends_tool_message_after_json_error(self) -> None:
        client = FakeClient(
            [
                make_response(
                    make_message(
                        tool_calls=[make_tool_call("call_1", "search_skill", "{bad json")]
                    )
                ),
                make_response(
                    make_message(
                        tool_calls=[
                            make_tool_call(
                                "call_2",
                                "finish_task",
                                '{"final_answer":"ok"}',
                            )
                        ]
                    )
                ),
            ]
        )
        agent = ThinkingAgent(client, "fake-model")

        with patch.object(agent.memory_manager, "search_experience", return_value=None), patch.object(
            agent.experience_agent, "process_experience_stream", return_value=[]
        ):
            result = agent.run("hello")

        self.assertEqual(result, "ok")
        second_call_messages = client.chat.completions.calls[1]["messages"]
        self.assertTrue(
            any(
                msg.get("role") == "tool"
                and msg.get("tool_call_id") == "call_1"
                and "Tool call failed" in msg.get("content", "")
                for msg in second_call_messages
                if isinstance(msg, dict)
            )
        )

    def test_thinking_agent_preserves_reasoning_content_between_tool_calls(self) -> None:
        client = FakeClient(
            [
                make_response(
                    make_message(
                        reasoning_content="private chain marker",
                        tool_calls=[make_tool_call("call_1", "search_skill", "{bad json")]
                    )
                ),
                make_response(
                    make_message(
                        tool_calls=[
                            make_tool_call(
                                "call_2",
                                "finish_task",
                                '{"final_answer":"ok"}',
                            )
                        ]
                    )
                ),
            ]
        )
        agent = ThinkingAgent(client, "fake-model")

        with patch.object(agent.memory_manager, "search_experience", return_value=None), patch.object(
            agent.experience_agent, "process_experience_stream", return_value=[]
        ):
            result = agent.run("hello")

        self.assertEqual(result, "ok")
        second_call_messages = client.chat.completions.calls[1]["messages"]
        self.assertTrue(
            any(
                isinstance(msg, dict)
                and msg.get("role") == "assistant"
                and msg.get("reasoning_content") == "private chain marker"
                for msg in second_call_messages
            )
        )

    def test_thinking_agent_adds_reasoning_content_for_legacy_deepseek_history(self) -> None:
        client = FakeClient([])
        agent = ThinkingAgent(client, "deepseek-v4-flash")
        agent.messages.append({"role": "assistant", "content": "legacy"})

        messages = agent._messages_for_llm(None)

        self.assertEqual(messages[-1]["reasoning_content"], "")
        self.assertNotIn("reasoning_content", agent.messages[-1])

    def test_thinking_agent_does_not_add_reasoning_content_for_other_models(self) -> None:
        client = FakeClient([])
        agent = ThinkingAgent(client, "fake-model")
        agent.messages.append({"role": "assistant", "content": "legacy"})

        messages = agent._messages_for_llm(None)

        self.assertNotIn("reasoning_content", messages[-1])

    def test_execution_agent_appends_tool_message_after_execute_error(self) -> None:
        client = FakeClient(
            [
                make_response(
                    make_message(
                        tool_calls=[
                            make_tool_call("call_exec", "failing_tool", '{"value": 1}')
                        ]
                    )
                ),
                make_response(make_message(content="done")),
            ]
        )
        agent = ExecutionAgent(client, "fake-model")

        with patch.object(agent.memory_manager, "search_experience", return_value=None), patch.object(
            agent.experience_agent, "process_experience_stream", return_value=[]
        ), patch("models.execution_agent.registry.get_skill_info", return_value=None), patch(
            "models.execution_agent.registry.execute",
            side_effect=RuntimeError("boom"),
        ):
            result = agent.run("do it")

        self.assertEqual(result, "done")
        second_call_messages = client.chat.completions.calls[1]["messages"]
        self.assertTrue(
            any(
                getattr(msg, "role", None) == "tool"
                or (
                    isinstance(msg, dict)
                    and msg.get("role") == "tool"
                    and msg.get("tool_call_id") == "call_exec"
                    and "Tool call failed" in msg.get("content", "")
                )
                for msg in second_call_messages
            )
        )

    def test_execution_agent_merges_injected_experience_into_single_system_message(self) -> None:
        client = FakeClient([make_response(make_message(content="done"))])
        agent = ExecutionAgent(client, "fake-model")

        with patch.object(
            agent.memory_manager, "search_experience", return_value="历史经验"
        ), patch.object(
            agent.experience_agent, "process_experience_stream", return_value=[]
        ):
            result = agent.run("do it")

        self.assertEqual(result, "done")
        first_call_messages = client.chat.completions.calls[0]["messages"]
        system_messages = [
            msg for msg in first_call_messages if isinstance(msg, dict) and msg.get("role") == "system"
        ]
        self.assertEqual(len(system_messages), 1)
        self.assertIn("历史经验", system_messages[0].get("content", ""))

    def test_execution_agent_appends_tool_message_after_shell_arg_validation_error(self) -> None:
        client = FakeClient(
            [
                make_response(
                    make_message(
                        tool_calls=[
                            make_tool_call(
                                "call_shell",
                                "shell_command",
                                '{"command":"git status","cwd":"../outside"}',
                            )
                        ]
                    )
                ),
                make_response(make_message(content="done")),
            ]
        )
        with tempfile.TemporaryDirectory() as workspace:
            agent = ExecutionAgent(client, "fake-model")
            agent.workspace = workspace

            with patch.object(
                agent.memory_manager, "search_experience", return_value=None
            ), patch.object(
                agent.experience_agent, "process_experience_stream", return_value=[]
            ):
                result = agent.run("check workspace")

        self.assertEqual(result, "done")
        second_call_messages = client.chat.completions.calls[1]["messages"]
        self.assertTrue(
            any(
                isinstance(msg, dict)
                and msg.get("role") == "tool"
                and msg.get("tool_call_id") == "call_shell"
                and "Tool call failed" in msg.get("content", "")
                for msg in second_call_messages
            )
        )

    def test_dag_agent_appends_tool_message_after_json_error(self) -> None:
        client = FakeClient(
            [
                make_response(
                    make_message(
                        tool_calls=[make_tool_call("call_dag", "create_task", "{bad json")]
                    )
                ),
                make_response(
                    make_message(
                        tool_calls=[
                            make_tool_call(
                                "call_dag_2",
                                "create_task",
                                '{"tasks":[{"id":"task_1","type":"agent","instruction":"do","dependencies":[]}]}',
                            )
                        ]
                    )
                ),
            ]
        )
        agent = DAGAgent(client, "fake-model")

        gen = agent.generate_dag_stream("plan")
        result = None
        try:
            while True:
                status, payload = next(gen)
                if status == "FINISHED":
                    result = payload
                    break
        except StopIteration as e:
            result = e.value

        self.assertEqual(result[0]["id"], "task_1")
        second_call_messages = client.chat.completions.calls[1]["messages"]
        self.assertTrue(
            any(
                getattr(msg, "role", None) == "tool"
                or (
                    isinstance(msg, dict)
                    and msg.get("role") == "tool"
                    and msg.get("tool_call_id") == "call_dag"
                    and "Tool call failed" in msg.get("content", "")
                )
                for msg in second_call_messages
            )
        )


if __name__ == "__main__":
    unittest.main()
