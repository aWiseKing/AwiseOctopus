import unittest
from types import SimpleNamespace

from models.safety_checker import is_action_safe


class _FakeCompletions:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if not self.responses:
            raise AssertionError("No fake responses left.")
        return self.responses.pop(0)


class _FakeClient:
    def __init__(self, responses):
        self.chat = SimpleNamespace(completions=_FakeCompletions(responses))


def _make_response(content: str):
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=content))]
    )


class TestSafetyChecker(unittest.TestCase):
    def test_shell_readonly_command_is_safe_without_llm(self) -> None:
        client = _FakeClient([])

        result = is_action_safe(
            client,
            "fake-model",
            "shell_command",
            {"command": "git status", "cwd": "."},
        )

        self.assertTrue(result)
        self.assertEqual(client.chat.completions.calls, [])

    def test_shell_unsafe_command_is_blocked_without_llm(self) -> None:
        client = _FakeClient([])

        result = is_action_safe(
            client,
            "fake-model",
            "shell_command",
            {"command": "rm -rf demo", "cwd": "."},
        )

        self.assertFalse(result)
        self.assertEqual(client.chat.completions.calls, [])

    def test_shell_unknown_command_falls_back_to_llm(self) -> None:
        client = _FakeClient([_make_response("SAFE")])

        result = is_action_safe(
            client,
            "fake-model",
            "shell_command",
            {"command": "custom-tool inspect", "cwd": "."},
        )

        self.assertTrue(result)
        self.assertEqual(len(client.chat.completions.calls), 1)


if __name__ == "__main__":
    unittest.main()
