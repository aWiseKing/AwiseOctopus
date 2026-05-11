import json
import tempfile
import unittest

from fastapi.testclient import TestClient

from api_server import create_app
from models.api_runtime import AgentApiRuntime, NDJSON_MEDIA_TYPE
from models.session_store import SessionStore
from tests.test_api_runtime import FakeSession


class TestApiServer(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.store = SessionStore(db_path=f"{self.tempdir.name}/session.db")
        runtime = AgentApiRuntime(
            store=self.store,
            session_factory=FakeSession,
            client_factory=lambda: object(),
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


if __name__ == "__main__":
    unittest.main()
