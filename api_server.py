from __future__ import annotations

from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from models.api_runtime import (
    NDJSON_MEDIA_TYPE,
    AgentApiRuntime,
    ApiConflictError,
    ApiNotFoundError,
    ApiValidationError,
    encode_ndjson,
)


class SendPromptRequest(BaseModel):
    sessionId: str
    prompt: str


class ReplyToAskUserRequest(BaseModel):
    sessionId: str
    reply: str


class ApprovalDecisionRequest(BaseModel):
    sessionId: str
    decision: str


def create_app(runtime: AgentApiRuntime | None = None) -> FastAPI:
    app = FastAPI(title="AwiseOctopus Agent API")
    app.state.runtime = runtime or AgentApiRuntime()

    app.add_middleware(
        CORSMiddleware,
        allow_origin_regex=r"https?://(localhost|127\.0\.0\.1)(:\d+)?",
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/api/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/sessions")
    async def list_sessions() -> list[dict[str, Any]]:
        return await app.state.runtime.list_sessions()

    @app.post("/api/sessions")
    async def create_session() -> dict[str, Any]:
        return await app.state.runtime.create_session()

    @app.get("/api/sessions/{session_id}/messages")
    async def load_session_history(session_id: str) -> list[dict[str, Any]]:
        try:
            return await app.state.runtime.load_session_history(session_id)
        except ApiNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/api/memory")
    async def list_memory(
        mode: str | None = None,
        sessionId: str | None = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        try:
            return await app.state.runtime.list_memories(
                mode=mode,
                session_id=sessionId,
                limit=limit,
            )
        except ApiValidationError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @app.delete("/api/memory")
    async def clear_memory(
        mode: str | None = None,
        sessionId: str | None = None,
    ) -> dict[str, Any]:
        try:
            return await app.state.runtime.clear_memories(
                mode=mode,
                session_id=sessionId,
            )
        except ApiValidationError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @app.get("/api/memory/{memory_id}")
    async def get_memory(memory_id: str) -> dict[str, Any]:
        try:
            return await app.state.runtime.get_memory(memory_id)
        except ApiNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.delete("/api/memory/{memory_id}")
    async def delete_memory(memory_id: str) -> dict[str, Any]:
        try:
            return await app.state.runtime.delete_memory(memory_id)
        except ApiNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/api/agent/send-prompt")
    async def send_prompt(request: SendPromptRequest) -> StreamingResponse:
        try:
            await app.state.runtime.assert_can_send_prompt(request.sessionId)
        except ApiConflictError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return _ndjson_response(
            app.state.runtime.send_prompt_stream(
                session_id=request.sessionId,
                prompt=request.prompt,
            )
        )

    @app.post("/api/agent/reply-to-ask-user")
    async def reply_to_ask_user(request: ReplyToAskUserRequest) -> StreamingResponse:
        try:
            await app.state.runtime.assert_can_reply(request.sessionId)
        except ApiConflictError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return _ndjson_response(
            app.state.runtime.reply_to_ask_user_stream(
                session_id=request.sessionId,
                reply=request.reply,
            )
        )

    @app.post("/api/agent/approval-decision")
    async def approval_decision(request: ApprovalDecisionRequest) -> StreamingResponse:
        try:
            await app.state.runtime.assert_can_submit_approval(
                request.sessionId,
                request.decision,
            )
        except ApiValidationError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        except ApiConflictError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return _ndjson_response(
            app.state.runtime.approval_decision_stream(
                session_id=request.sessionId,
                decision=request.decision,
            )
        )

    return app


def _ndjson_response(event_stream) -> StreamingResponse:
    async def body():
        async for event in event_stream:
            yield encode_ndjson(event)

    return StreamingResponse(body(), media_type=NDJSON_MEDIA_TYPE)


app = create_app()
