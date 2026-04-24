import tempfile
import unittest

from models.session_store import SessionStore


class TestSessionStore(unittest.TestCase):
    def test_roundtrip_order(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db_path = f"{td}/session.db"
            store = SessionStore(db_path=db_path)
            session_id = "s-test"

            messages = [
                {"role": "user", "content": "hi"},
                {"role": "assistant", "content": "hello"},
                {"role": "tool", "tool_call_id": "t1", "content": "ok"},
            ]
            for m in messages:
                store.append_message(session_id, m)

            loaded = store.load_messages(session_id)
            self.assertEqual(loaded, messages)
            store.close()

    def test_name_and_current(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db_path = f"{td}/session.db"
            store = SessionStore(db_path=db_path)
            store.create_session("s1", name="n1")
            store.create_session("s2", name="n2")
            self.assertEqual(store.resolve_session("n2"), "s2")
            store.set_current("s2")
            self.assertEqual(store.get_current(), "s2")
            store.close()


if __name__ == "__main__":
    unittest.main()
