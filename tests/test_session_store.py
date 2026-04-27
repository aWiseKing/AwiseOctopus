import tempfile
import unittest

from models.session_store import SessionStore


class TestSessionStore(unittest.TestCase):
    def test_roundtrip_order(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db_path = f"{td}/session.db"
            store = SessionStore(db_path=db_path)
            try:
                session_id = "s-test"

                messages = [
                    {"role": "user", "content": "hi"},
                    {
                        "role": "assistant",
                        "content": "",
                        "tool_calls": [
                            {
                                "id": "t1",
                                "type": "function",
                                "function": {"name": "demo", "arguments": "{}"},
                            }
                        ],
                    },
                    {"role": "tool", "tool_call_id": "t1", "content": "ok"},
                ]
                for m in messages:
                    store.append_message(session_id, m)

                loaded = store.load_messages(session_id)
                self.assertEqual(loaded, messages)
            finally:
                store.close()

    def test_name_and_current(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db_path = f"{td}/session.db"
            store = SessionStore(db_path=db_path)
            try:
                store.create_session("s1", name="n1")
                store.create_session("s2", name="n2")
                self.assertEqual(store.resolve_session("n2"), "s2")
                store.set_current("s2")
                self.assertEqual(store.get_current(), "s2")
            finally:
                store.close()

    def test_load_messages_keeps_valid_tool_sequence(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db_path = f"{td}/session.db"
            store = SessionStore(db_path=db_path)
            try:
                session_id = "s-valid"

                messages = [
                    {"role": "user", "content": "hi"},
                    {
                        "role": "assistant",
                        "content": "",
                        "tool_calls": [
                            {
                                "id": "call_1",
                                "type": "function",
                                "function": {"name": "search_skill", "arguments": "{}"},
                            }
                        ],
                    },
                    {"role": "tool", "tool_call_id": "call_1", "name": "search_skill", "content": "ok"},
                    {"role": "assistant", "content": "done"},
                ]
                for m in messages:
                    store.append_message(session_id, m)

                loaded = store.load_messages(session_id)
                self.assertEqual(loaded, messages)
            finally:
                store.close()

    def test_load_messages_filters_broken_tool_sequence(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db_path = f"{td}/session.db"
            store = SessionStore(db_path=db_path)
            try:
                session_id = "s-broken"

                messages = [
                    {"role": "user", "content": "first"},
                    {
                        "role": "assistant",
                        "content": "",
                        "tool_calls": [
                            {
                                "id": "call_broken",
                                "type": "function",
                                "function": {"name": "execute_subtask", "arguments": "{}"},
                            }
                        ],
                    },
                    {"role": "assistant", "content": "this should be ignored"},
                    {"role": "tool", "tool_call_id": "orphan", "name": "x", "content": "bad"},
                    {"role": "user", "content": "second"},
                    {"role": "assistant", "content": "recovered"},
                ]
                for m in messages:
                    store.append_message(session_id, m)

                loaded = store.load_messages(session_id)
                self.assertEqual(
                    loaded,
                    [
                        {"role": "user", "content": "first"},
                        {"role": "user", "content": "second"},
                        {"role": "assistant", "content": "recovered"},
                    ],
                )
            finally:
                store.close()


if __name__ == "__main__":
    unittest.main()
