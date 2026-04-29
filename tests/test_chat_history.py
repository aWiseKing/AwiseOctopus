import tempfile
import unittest

from cli_rich.commands.chat import _create_prompt_session
from models.session_store import SessionStore


class _FakeFileHistory:
    def __init__(self, filename: str) -> None:
        self.filename = filename


class _FakePromptSession:
    def __init__(self, *, history) -> None:
        self.history = history


class TestChatHistory(unittest.TestCase):
    def test_create_prompt_session_uses_session_history_file(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db_path = f"{td}/session.db"
            store = SessionStore(db_path=db_path)
            try:
                prompt_session = _create_prompt_session(
                    store,
                    "chat-session",
                    _FakePromptSession,
                    _FakeFileHistory,
                )

                history = prompt_session.history
                history_filename = history.filename

                self.assertEqual(
                    history_filename,
                    store.get_prompt_history_path("chat-session"),
                )
            finally:
                store.close()


if __name__ == "__main__":
    unittest.main()
