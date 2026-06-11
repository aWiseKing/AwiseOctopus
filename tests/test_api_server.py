import json
import tempfile
import unittest

from fastapi.testclient import TestClient

from api_server import create_app
from models.api_runtime import AgentApiRuntime, NDJSON_MEDIA_TYPE
from models.memory import MemoryManager
from models.session_store import SessionStore
from tests.test_api_runtime import FakeSession


class TestApiServer(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.store = SessionStore(db_path=f"{self.tempdir.name}/session.db")
        self.memory_manager = MemoryManager(
            db_path=f"{self.tempdir.name}/experience.db",
            chroma_path=f"{self.tempdir.name}/vec",
        )
        runtime = AgentApiRuntime(
            store=self.store,
            session_factory=FakeSession,
            client_factory=lambda: object(),
            memory_manager=self.memory_manager,
            model="fake-model",
        )
        self.client = TestClient(create_app(runtime))

    def tearDown(self):
        self.store.close()
        self.tempdir.cleanup()

    def test_session_endpoints_return_flutter_contract_shape(self):
        created = self.client.post("/api/sessions")
        self.assertEqual(created.status_code, 200)
        session_id = created.json()["id"]

        listed = self.client.get("/api/sessions")
        messages = self.client.get(f"/api/sessions/{session_id}/messages")

        self.assertEqual(listed.status_code, 200)
        self.assertEqual(messages.status_code, 200)
        self.assertEqual(listed.json()[0]["id"], session_id)
        self.assertEqual(messages.json(), [])

    def test_send_prompt_returns_ndjson_events(self):
        response = self.client.post(
            "/api/agent/send-prompt",
            json={"sessionId": "s-http", "prompt": "hello"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn(NDJSON_MEDIA_TYPE, response.headers["content-type"])
        events = [
            json.loads(line)
            for line in response.text.splitlines()
            if line.strip()
        ]
        self.assertEqual(
            [event["type"] for event in events],
            ["thinking_log", "final_answer"],
        )

    def test_memory_endpoints(self):
        memory_id = self.memory_manager.add_memory(
            mode="long_term",
            scope="project_context",
            content="项目正在升级 memory。",
            summary="memory 升级",
            confidence=0.9,
            importance=0.9,
        )

        listed = self.client.get("/api/memory?mode=long&limit=5")
        shown = self.client.get(f"/api/memory/{memory_id}")
        deleted = self.client.delete(f"/api/memory/{memory_id}")
        missing = self.client.get(f"/api/memory/{memory_id}")

        self.assertEqual(listed.status_code, 200)
        self.assertEqual(listed.json()[0]["id"], memory_id)
        self.assertEqual(shown.status_code, 200)
        self.assertEqual(shown.json()["createdAt"], shown.json()["updatedAt"])
        self.assertEqual(deleted.json(), {"deleted": True, "id": memory_id})
        self.assertEqual(missing.status_code, 404)

    def test_send_prompt_returns_fatal_abort_event(self):
        response = self.client.post(
            "/api/agent/send-prompt",
            json={"sessionId": "s-http-abort", "prompt": "abort"},
        )

        self.assertEqual(response.status_code, 200)
        events = [
            json.loads(line)
            for line in response.text.splitlines()
            if line.strip()
        ]
        self.assertEqual(events[-1]["type"], "error")
        self.assertTrue(events[-1]["fatal"])
        self.assertTrue(events[-1]["shouldReturnToChat"])
        self.assertEqual(events[-1]["errorCode"], "llm_rate_limited")


if __name__ == "__main__":
    unittest.main()
