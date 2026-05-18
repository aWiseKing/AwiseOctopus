from __future__ import annotations

import asyncio
import json
import os
import threading
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable

from openai import OpenAI

from cli_rich.model_registry import get_active_api_key, infer_provider
from .agent_errors import AgentOperationAbortedError, abort_message_for_user
from .config_manager import ConfigManager
from .interaction import APPROVAL_CHOICES, create_approval_handler
from .session import Session
from .session_store import SessionStore


NDJSON_MEDIA_TYPE = "application/x-ndjson"


def encode_ndjson(event: dict[str, Any]) -> str:
    return json.dumps(event, ensure_ascii=False, separators=(",", ":")) + "\n"


class ApiConflictError(RuntimeError):
    pass


class ApiNotFoundError(RuntimeError):
    pass


class ApiValidationError(ValueError):
    pass


@dataclass
class _PendingApproval:
    event: threading.Event
    decision: str | None = None


@dataclass
class ApiSessionState:
    session_id: str
    session: Any
    approval_handler: Any
    phase: str = "idle"
    thinking_gen: Any | None = None
    event_queue: asyncio.Queue[dict[str, Any]] = field(default_factory=asyncio.Queue)
    event_loop: asyncio.AbstractEventLoop | None = None
    pending_approval: _PendingApproval | None = None
    dag_task: asyncio.Task | None = None
    dag_prompt: str | None = None

    @property
    def is_busy_for_new_prompt(self) -> bool:
        return self.phase in {"thinking", "awaiting_user", "dag_running", "awaiting_approval"}


class AgentApiRuntime:
    def __init__(
        self,
        *,
        store: SessionStore | None = None,
        session_factory: Callable[..., Any] | None = None,
        client_factory: Callable[[], Any] | None = None,
        model: str | None = None,
    ) -> None:
        self.store = store or SessionStore()
        self._session_factory = session_factory or Session
        self._client_factory = client_factory or self._create_openai_client
        self._model = model
        self._client: Any | None = None
        self._states: dict[str, ApiSessionState] = {}
        self._lock = asyncio.Lock()

    def close(self) -> None:
        self.store.close()

    def _create_openai_client(self) -> OpenAI:
        config_mgr = ConfigManager()
        api_key = config_mgr.get("api_key") or os.getenv("api_key")
        base_url = (
            config_mgr.get("base_url")
            or os.getenv("base_url")
            or "https://dashscope.aliyuncs.com/compatible-mode/v1"
        )
        provider = infer_provider(base_url=base_url, model=self._get_model())
        api_key = get_active_api_key(provider, config_mgr)
        return OpenAI(api_key=api_key, base_url=base_url)

    def _get_model(self) -> str:
        if self._model:
            return self._model
        config_mgr = ConfigManager()
        return config_mgr.get("MODEL") or os.getenv("MODEL") or "glm-5"

    def _get_client(self) -> Any:
        if self._client is None:
            self._client = self._client_factory()
        return self._client

    def _make_session(self, session_id: str) -> ApiSessionState:
        state_ref: dict[str, ApiSessionState] = {}

        def approval_prompt(payload: dict[str, Any]) -> str:
            state = state_ref["state"]
            pending = _PendingApproval(event=threading.Event())
            state.pending_approval = pending
            state.phase = "awaiting_approval"
            approval_request = dict(payload)
            approval_request.setdefault("id", f"approval-{uuid.uuid4()}")
            event = {
                "type": "approval_request",
                "approvalRequest": approval_request,
            }
            pause = {"__pause": "approval"}
            if state.event_loop and state.event_loop.is_running():
                state.event_loop.call_soon_threadsafe(state.event_queue.put_nowait, event)
                state.event_loop.call_soon_threadsafe(state.event_queue.put_nowait, pause)
            else:
                state.event_queue.put_nowait(event)
                state.event_queue.put_nowait(pause)
            pending.event.wait()
            return pending.decision or "no"

        approval_handler = create_approval_handler(
            approval_prompt,
            session_id=session_id,
        )
        session = self._session_factory(
            self._get_client(),
            self._get_model(),
            session_id=session_id,
            interaction_handler=approval_handler,
        )
        state = ApiSessionState(
            session_id=session_id,
            session=session,
            approval_handler=approval_handler,
        )
        state_ref["state"] = state
        return state

    async def _get_or_create_state(self, session_id: str) -> ApiSessionState:
        async with self._lock:
            state = self._states.get(session_id)
            if state is None:
                resolved = self.store.resolve_session(session_id)
                if resolved is None:
                    self.store.create_session(session_id)
                state = self._make_session(session_id)
                self._states[session_id] = state
            return state

    async def list_sessions(self) -> list[dict[str, Any]]:
        return [self._session_summary(item) for item in self.store.list_sessions()]

    async def create_session(self) -> dict[str, Any]:
        session_id = f"session-{uuid.uuid4()}"
        self.store.create_session(session_id)
        await self._get_or_create_state(session_id)
        return self._session_summary(
            {
                "session_id": session_id,
                "name": None,
                "updated_at": None,
            }
        )

    async def load_session_history(self, session_id: str) -> list[dict[str, Any]]:
        if self.store.resolve_session(session_id) is None:
            raise ApiNotFoundError(f"Session not found: {session_id}")
        return self.store.list_client_messages(session_id)

    def _session_summary(self, item: dict[str, Any]) -> dict[str, Any]:
        session_id = item["session_id"]
        messages = self.store.list_client_messages(session_id)
        preview = messages[-1]["content"] if messages else ""
        return {
            "id": session_id,
            "title": item.get("name") or "新会话",
            "preview": preview,
            "lastUpdated": item.get("updated_at") or _utc_now_iso(),
        }

    async def assert_can_send_prompt(self, session_id: str) -> None:
        state = await self._get_or_create_state(session_id)
        if state.is_busy_for_new_prompt:
            raise ApiConflictError(f"Session {session_id} already has an active flow.")

    async def assert_can_reply(self, session_id: str) -> None:
        state = await self._get_or_create_state(session_id)
        if state.phase != "awaiting_user" or state.thinking_gen is None:
            raise ApiConflictError(f"Session {session_id} is not waiting for a user reply.")

    async def assert_can_submit_approval(self, session_id: str, decision: str) -> None:
        if decision not in APPROVAL_CHOICES:
            raise ApiValidationError("decision must be one of: session, only, no")
        state = await self._get_or_create_state(session_id)
        if state.phase != "awaiting_approval" or state.pending_approval is None:
            raise ApiConflictError(f"Session {session_id} is not waiting for approval.")

    async def send_prompt_stream(self, *, session_id: str, prompt: str):
        state = await self._get_or_create_state(session_id)
        if state.is_busy_for_new_prompt:
            yield {"type": "error", "text": f"Session {session_id} already has an active flow."}
            return
        state.phase = "thinking"
        state.event_loop = asyncio.get_running_loop()
        state.dag_prompt = prompt
        state.thinking_gen = state.session.think_stream(prompt)
        async for event in self._continue_thinking(state):
            yield event

    async def reply_to_ask_user_stream(self, *, session_id: str, reply: str):
        state = await self._get_or_create_state(session_id)
        if state.phase != "awaiting_user" or state.thinking_gen is None:
            yield {"type": "error", "text": f"Session {session_id} is not waiting for a user reply."}
            return
        state.phase = "thinking"
        state.event_loop = asyncio.get_running_loop()
        async for event in self._continue_thinking(state, send_value=reply):
            yield event

    async def approval_decision_stream(self, *, session_id: str, decision: str):
        state = await self._get_or_create_state(session_id)
        if decision not in APPROVAL_CHOICES:
            yield {"type": "error", "text": "decision must be one of: session, only, no"}
            return
        if state.phase != "awaiting_approval" or state.pending_approval is None:
            yield {"type": "error", "text": f"Session {session_id} is not waiting for approval."}
            return
        pending = state.pending_approval
        pending.decision = decision
        state.pending_approval = None
        state.phase = "dag_running"
        state.event_loop = asyncio.get_running_loop()
        pending.event.set()
        async for event in self._drain_dag_events(state):
            yield event

    async def _continue_thinking(self, state: ApiSessionState, send_value: str | None = None):
        try:
            pending_send = send_value
            while True:
                status, payload = await asyncio.to_thread(
                    _advance_generator,
                    state.thinking_gen,
                    pending_send,
                )
                if status == "__STOP__":
                    state.phase = "idle"
                    state.thinking_gen = None
                    if payload is not None:
                        yield {"type": "final_answer", "text": str(payload)}
                    return
                pending_send = None
                if status == "RUNNING":
                    yield {"type": "thinking_log", "text": str(payload)}
                elif status == "ASK_USER":
                    state.phase = "awaiting_user"
                    yield {"type": "ask_user", "text": str(payload)}
                    return
                elif status == "FINISHED":
                    state.thinking_gen = None
                    if isinstance(payload, list):
                        yield {"type": "dag_planned", "tasks": payload}
                        state.phase = "dag_running"
                        state.dag_task = asyncio.create_task(
                            self._run_dag_and_summary(state, payload)
                        )
                        async for event in self._drain_dag_events(state):
                            yield event
                    else:
                        state.phase = "idle"
                        yield {"type": "final_answer", "text": str(payload)}
                    return
        except AgentOperationAbortedError as exc:
            state.phase = "idle"
            state.thinking_gen = None
            yield {
                "type": "error",
                "text": abort_message_for_user(exc),
                "errorCode": exc.code,
                "fatal": True,
                "shouldReturnToChat": True,
            }
        except Exception as exc:
            state.phase = "idle"
            state.thinking_gen = None
            yield {"type": "error", "text": f"{type(exc).__name__}: {exc}"}

    async def _run_dag_and_summary(self, state: ApiSessionState, tasks: list[dict[str, Any]]) -> None:
        try:
            def on_status_change(status: dict[str, Any]) -> None:
                state.event_queue.put_nowait(
                    {"type": "dag_status", "dagStatus": status}
                )

            results = await state.session.execute_dag_async(
                tasks,
                on_status_change=on_status_change,
                interaction_handler=state.approval_handler,
            )
            await state.event_queue.put({"type": "dag_result", "rawPayload": results})

            summary_text = ""
            summary_gen = state.session.summarize_stream(state.dag_prompt or "", results)
            while True:
                has_chunk, chunk = await asyncio.to_thread(_next_generator_value, summary_gen)
                if not has_chunk:
                    break
                summary_text += str(chunk)
                await state.event_queue.put({"type": "summary_chunk", "text": str(chunk)})

            await state.event_queue.put({"type": "final_answer", "text": summary_text})
        except AgentOperationAbortedError as exc:
            await state.event_queue.put(
                {
                    "type": "error",
                    "text": abort_message_for_user(exc),
                    "errorCode": exc.code,
                    "fatal": True,
                    "shouldReturnToChat": True,
                }
            )
        except Exception as exc:
            await state.event_queue.put({"type": "error", "text": f"{type(exc).__name__}: {exc}"})
        finally:
            state.phase = "idle"
            state.dag_task = None
            await state.event_queue.put({"__done": True})

    async def _drain_dag_events(self, state: ApiSessionState):
        while True:
            event = await state.event_queue.get()
            if "__pause" in event:
                return
            if "__done" in event:
                return
            yield event


def _advance_generator(gen: Any, send_value: str | None):
    try:
        if send_value is None:
            return next(gen)
        return gen.send(send_value)
    except StopIteration as exc:
        return "__STOP__", exc.value


def _next_generator_value(gen: Any) -> tuple[bool, Any]:
    try:
        return True, next(gen)
    except StopIteration:
        return False, None


def _utc_now_iso() -> str:
    import datetime

    return datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z")
