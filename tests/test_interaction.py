import unittest

from models.interaction import (
    APPROVAL_NO,
    APPROVAL_ONLY,
    APPROVAL_SESSION,
    build_confirmation_request,
    create_approval_handler,
    format_rejection_message,
)


class TestInteractionApproval(unittest.TestCase):
    def test_only_allows_current_operation_only(self) -> None:
        handler = create_approval_handler(lambda request: APPROVAL_ONLY, session_id="s1")

        first = handler("python_eval", {"code": "print('hi')", "use_sandbox": False})
        second = handler("python_eval", {"code": "print('again')", "use_sandbox": False})

        self.assertTrue(first.allow_current)
        self.assertFalse(first.allow_future_in_session)
        self.assertTrue(second.allow_current)
        self.assertEqual(second.source, "user")

    def test_session_auto_allows_later_non_delete_operations(self) -> None:
        calls = []

        def choose_session(request):
            calls.append(request["tool_name"])
            return APPROVAL_SESSION

        handler = create_approval_handler(choose_session, session_id="s1")

        first = handler("python_eval", {"code": "print('hi')", "use_sandbox": False})
        second = handler("python_eval", {"code": "print('again')", "use_sandbox": False})

        self.assertTrue(first.allow_current)
        self.assertTrue(first.allow_future_in_session)
        self.assertEqual(second.source, "session_default")
        self.assertEqual(calls, ["python_eval"])

    def test_session_does_not_auto_allow_delete_operation(self) -> None:
        calls = []

        def choose_session(request):
            calls.append(request["tool_name"])
            return APPROVAL_SESSION

        handler = create_approval_handler(choose_session, session_id="s1")

        handler("python_eval", {"code": "print('safe')", "use_sandbox": False})
        delete_decision = handler(
            "python_eval",
            {"code": "import os\nos.remove('demo.txt')", "use_sandbox": False},
        )

        self.assertTrue(delete_decision.allow_current)
        self.assertFalse(delete_decision.allow_future_in_session)
        self.assertEqual(delete_decision.source, "user")
        self.assertEqual(calls, ["python_eval", "python_eval"])

    def test_no_rejects_current_operation(self) -> None:
        handler = create_approval_handler(lambda request: APPROVAL_NO, session_id="s1")

        decision = handler("python_eval", {"code": "print('hi')", "use_sandbox": False})

        self.assertFalse(decision.allow_current)
        self.assertEqual(format_rejection_message(decision), "操作被拒绝：用户选择 no。")

    def test_delete_request_disables_session_persistence(self) -> None:
        request = build_confirmation_request(
            "python_eval",
            {"code": "import shutil\nshutil.rmtree('demo')", "use_sandbox": False},
        )

        self.assertTrue(request.is_delete_operation)
        self.assertFalse(request.session_choice_enabled)

    def test_shell_delete_request_disables_session_persistence(self) -> None:
        request = build_confirmation_request(
            "shell_command",
            {"command": "Remove-Item demo.txt", "cwd": "."},
        )

        self.assertTrue(request.is_delete_operation)
        self.assertFalse(request.session_choice_enabled)

    def test_shell_session_auto_allows_later_non_delete_operations(self) -> None:
        calls = []

        def choose_session(request):
            calls.append(request["tool_name"])
            return APPROVAL_SESSION

        handler = create_approval_handler(choose_session, session_id="s1")

        first = handler("shell_command", {"command": "git status", "cwd": "."})
        second = handler("shell_command", {"command": "dir", "cwd": "."})

        self.assertTrue(first.allow_current)
        self.assertTrue(first.allow_future_in_session)
        self.assertEqual(second.source, "session_default")
        self.assertEqual(calls, ["shell_command"])

    def test_shell_delete_does_not_reuse_session_default(self) -> None:
        calls = []

        def choose_session(request):
            calls.append(request["tool_name"])
            return APPROVAL_SESSION

        handler = create_approval_handler(choose_session, session_id="s1")

        handler("shell_command", {"command": "git status", "cwd": "."})
        delete_decision = handler(
            "shell_command",
            {"command": "rm -rf demo", "cwd": "."},
        )

        self.assertTrue(delete_decision.allow_current)
        self.assertFalse(delete_decision.allow_future_in_session)
        self.assertEqual(delete_decision.source, "user")
        self.assertEqual(calls, ["shell_command", "shell_command"])


if __name__ == "__main__":
    unittest.main()
