from __future__ import annotations

from typing import Iterable

try:
    from openai import (
        APIConnectionError,
        APIError,
        APIStatusError,
        APITimeoutError,
        AuthenticationError,
        BadRequestError,
        InternalServerError,
        PermissionDeniedError,
        RateLimitError,
    )

    OPENAI_PROVIDER_ERROR_TYPES: tuple[type[BaseException], ...] = (
        APIError,
        APIConnectionError,
        APIStatusError,
        APITimeoutError,
        AuthenticationError,
        BadRequestError,
        InternalServerError,
        PermissionDeniedError,
        RateLimitError,
    )
except ImportError:  # pragma: no cover - defensive fallback for environments without openai
    OPENAI_PROVIDER_ERROR_TYPES = ()


class AgentOperationAbortedError(RuntimeError):
    """A user-facing fatal error that should stop the current agent flow."""

    def __init__(
        self,
        message: str,
        *,
        code: str = "agent_operation_aborted",
        detail: str | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.detail = detail or message


def abort_message_for_user(exc: Exception) -> str:
    if isinstance(exc, AgentOperationAbortedError):
        return str(exc)
    return (
        f"{type(exc).__name__}: {exc}\n"
        "Agent 操作已中止，请回到对话框后继续操作。"
    )


def is_agent_abort_error(exc: Exception) -> bool:
    return isinstance(exc, AgentOperationAbortedError)


def raise_if_agent_abort_error(exc: Exception) -> None:
    if is_agent_abort_error(exc):
        raise exc


def create_chat_completion(client, *, stage: str, **kwargs):
    try:
        return client.chat.completions.create(**kwargs)
    except Exception as exc:
        converted = convert_to_agent_abort_error(exc, stage=stage)
        if converted is not None:
            raise converted from exc
        raise


def iter_chat_completion_stream(response, *, stage: str) -> Iterable:
    try:
        for chunk in response:
            yield chunk
    except Exception as exc:
        converted = convert_to_agent_abort_error(exc, stage=stage)
        if converted is not None:
            raise converted from exc
        raise


def convert_to_agent_abort_error(
    exc: Exception,
    *,
    stage: str,
) -> AgentOperationAbortedError | None:
    if isinstance(exc, AgentOperationAbortedError):
        return exc

    text = _exception_text(exc).lower()
    status_code = getattr(exc, "status_code", None)

    if _is_rate_limit_or_quota_error(exc, text, status_code):
        return AgentOperationAbortedError(
            (
                f"{stage} 调用模型服务失败：请求频率超限或额度已耗尽。"
                "Agent 操作已中止，请回到对话框后重试，或调整模型/配额后继续。"
            ),
            code="llm_rate_limited",
            detail=f"{type(exc).__name__}: {exc}",
        )

    if _is_auth_or_permission_error(exc, text, status_code):
        return AgentOperationAbortedError(
            (
                f"{stage} 调用模型服务失败：API Key 无效或当前账号无权限。"
                "Agent 操作已中止，请回到对话框后检查配置再继续。"
            ),
            code="llm_auth_failed",
            detail=f"{type(exc).__name__}: {exc}",
        )

    if _is_connectivity_error(exc, text, status_code):
        return AgentOperationAbortedError(
            (
                f"{stage} 调用模型服务失败：网络连接异常或请求超时。"
                "Agent 操作已中止，请回到对话框后重试。"
            ),
            code="llm_connection_failed",
            detail=f"{type(exc).__name__}: {exc}",
        )

    if _is_server_error(exc, text, status_code):
        return AgentOperationAbortedError(
            (
                f"{stage} 调用模型服务失败：上游服务暂时不可用。"
                "Agent 操作已中止，请回到对话框后稍后重试。"
            ),
            code="llm_service_unavailable",
            detail=f"{type(exc).__name__}: {exc}",
        )

    if _is_provider_error(exc, status_code, text):
        return AgentOperationAbortedError(
            (
                f"{stage} 调用模型服务失败。"
                "Agent 操作已中止，请回到对话框后检查模型配置或稍后重试。"
            ),
            code="llm_provider_error",
            detail=f"{type(exc).__name__}: {exc}",
        )

    return None


def _is_provider_error(exc: Exception, status_code, text: str) -> bool:
    if isinstance(exc, OPENAI_PROVIDER_ERROR_TYPES):
        return True
    if status_code is not None:
        return True
    provider_keywords = (
        "openai",
        "rate limit",
        "quota",
        "api key",
        "authentication",
        "permission",
        "timeout",
        "connection",
    )
    return any(keyword in text for keyword in provider_keywords)


def _is_rate_limit_or_quota_error(exc: Exception, text: str, status_code) -> bool:
    if OPENAI_PROVIDER_ERROR_TYPES:
        rate_limit_cls = tuple(
            cls for cls in OPENAI_PROVIDER_ERROR_TYPES if cls.__name__ == "RateLimitError"
        )
        if rate_limit_cls and isinstance(exc, rate_limit_cls):
            return True
    return status_code == 429 or any(
        keyword in text
        for keyword in (
            "rpm exhausted",
            "rate limit",
            "rate_limit",
            "quota_exceeded",
            "quota exceeded",
            "insufficient_quota",
            "too many requests",
        )
    )


def _is_auth_or_permission_error(exc: Exception, text: str, status_code) -> bool:
    if OPENAI_PROVIDER_ERROR_TYPES:
        auth_names = {"AuthenticationError", "PermissionDeniedError"}
        if type(exc).__name__ in auth_names and isinstance(exc, OPENAI_PROVIDER_ERROR_TYPES):
            return True
    return status_code in {401, 403} or any(
        keyword in text
        for keyword in (
            "authentication",
            "invalid api key",
            "api key",
            "permission denied",
            "forbidden",
            "unauthorized",
            "no permission",
        )
    )


def _is_connectivity_error(exc: Exception, text: str, status_code) -> bool:
    if OPENAI_PROVIDER_ERROR_TYPES:
        conn_names = {"APIConnectionError", "APITimeoutError"}
        if type(exc).__name__ in conn_names and isinstance(exc, OPENAI_PROVIDER_ERROR_TYPES):
            return True
    return status_code in {408, 504} or any(
        keyword in text
        for keyword in (
            "timed out",
            "timeout",
            "connection error",
            "connection reset",
            "connection aborted",
            "network",
            "dns",
            "connect",
        )
    )


def _is_server_error(exc: Exception, text: str, status_code) -> bool:
    if OPENAI_PROVIDER_ERROR_TYPES:
        if type(exc).__name__ == "InternalServerError" and isinstance(
            exc, OPENAI_PROVIDER_ERROR_TYPES
        ):
            return True
    return status_code in {500, 502, 503, 504} or any(
        keyword in text
        for keyword in (
            "internal server error",
            "server error",
            "service unavailable",
            "bad gateway",
            "gateway timeout",
            "overloaded",
        )
    )


def _exception_text(exc: Exception) -> str:
    body = getattr(exc, "body", None)
    if body is not None:
        return f"{type(exc).__name__}: {exc} {body}"
    return f"{type(exc).__name__}: {exc}"
