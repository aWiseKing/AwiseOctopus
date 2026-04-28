from __future__ import annotations

import json
import re
import sys
import threading
from dataclasses import dataclass
from inspect import Parameter, signature


APPROVAL_SESSION = "session"
APPROVAL_ONLY = "only"
APPROVAL_NO = "no"
APPROVAL_CHOICES = (APPROVAL_SESSION, APPROVAL_ONLY, APPROVAL_NO)

_DELETE_CODE_PATTERNS = [
    r"\bos\.remove\s*\(",
    r"\bos\.unlink\s*\(",
    r"\bpathlib\.Path\s*\([^)]*\)\.unlink\s*\(",
    r"\bPath\s*\([^)]*\)\.unlink\s*\(",
    r"\bshutil\.rmtree\s*\(",
    r"\bos\.rmdir\s*\(",
    r"\bsubprocess\.(?:run|Popen)\s*\([^)]*(?:rm|del|rmdir)",
]

_DELETE_SHELL_PATTERNS = [
    r"\b(?:rm|rmdir|del|erase)\b",
    r"\bRemove-Item\b",
]


@dataclass(frozen=True)
class ConfirmationRequest:
    tool_name: str
    args: dict
    is_delete_operation: bool
    session_choice_enabled: bool

    def to_prompt_payload(self) -> dict:
        return {
            "tool_name": self.tool_name,
            "args": self.args,
            "is_delete_operation": self.is_delete_operation,
            "session_choice_enabled": self.session_choice_enabled,
        }


@dataclass(frozen=True)
class ApprovalDecision:
    decision: str
    allow_current: bool
    allow_future_in_session: bool
    is_delete_operation: bool
    source: str = "user"


class ApprovalContext:
    def __init__(self, session_id: str | None = None):
        self.session_id = session_id
        self._session_default_allowed = False
        self._lock = threading.RLock()

    def set_session_id(self, session_id: str | None) -> None:
        with self._lock:
            if session_id != self.session_id:
                self.session_id = session_id
                self._session_default_allowed = False

    def should_auto_approve(self, request: ConfirmationRequest) -> bool:
        with self._lock:
            return self._session_default_allowed and not request.is_delete_operation

    def record_decision(self, request: ConfirmationRequest, decision: ApprovalDecision) -> ApprovalDecision:
        with self._lock:
            if decision.allow_future_in_session and not request.is_delete_operation:
                self._session_default_allowed = True
        return decision

    def has_session_default(self) -> bool:
        with self._lock:
            return self._session_default_allowed


class ApprovalHandler:
    def __init__(self, prompt_callback=None, session_id: str | None = None):
        self.prompt_callback = prompt_callback
        self.approval_context = ApprovalContext(session_id=session_id)

    def set_session_id(self, session_id: str | None) -> None:
        self.approval_context.set_session_id(session_id)

    def __call__(self, tool_name: str, args: dict | None = None) -> ApprovalDecision:
        request = build_confirmation_request(tool_name, args or {})

        if self.approval_context.should_auto_approve(request):
            return ApprovalDecision(
                decision=APPROVAL_SESSION,
                allow_current=True,
                allow_future_in_session=True,
                is_delete_operation=request.is_delete_operation,
                source="session_default",
            )

        if not self.prompt_callback:
            return ApprovalDecision(
                decision=APPROVAL_NO,
                allow_current=False,
                allow_future_in_session=False,
                is_delete_operation=request.is_delete_operation,
                source="missing_handler",
            )

        raw_decision = _invoke_prompt_callback(
            self.prompt_callback, request, request.to_prompt_payload()
        )
        decision = normalize_approval_decision(raw_decision, request)
        return self.approval_context.record_decision(request, decision)


def _default_cli_interaction_handler(request: dict) -> str:
    print(f"\n[⚠️ 警告] Agent 准备执行高危操作 `{request['tool_name']}`，参数为:")
    try:
        print(json.dumps(request["args"], indent=2, ensure_ascii=False))
    except Exception:
        print(str(request["args"]))
    if request["is_delete_operation"]:
        print("[提示] 检测到删除类操作，即使选择 session，也不会开启会话级默认同意。")
    print("请选择授权方式: session / only / no (默认: no)")
    return input("> ").strip() or APPROVAL_NO


def _invoke_prompt_callback(callback, request: ConfirmationRequest, payload: dict):
    try:
        callback_signature = signature(callback)
    except (TypeError, ValueError):
        callback_signature = None

    if callback_signature is None:
        return callback(payload)

    params = list(callback_signature.parameters.values())
    positional = [
        p
        for p in params
        if p.kind in (Parameter.POSITIONAL_ONLY, Parameter.POSITIONAL_OR_KEYWORD)
    ]
    has_varargs = any(p.kind == Parameter.VAR_POSITIONAL for p in params)
    if has_varargs or len(positional) <= 1:
        return callback(payload)
    return callback(request.tool_name, request.args)


def normalize_approval_decision(raw_decision, request: ConfirmationRequest) -> ApprovalDecision:
    if isinstance(raw_decision, ApprovalDecision):
        return raw_decision

    decision = str(raw_decision or APPROVAL_NO).strip().lower()
    if decision not in APPROVAL_CHOICES:
        decision = APPROVAL_NO

    allow_current = decision in (APPROVAL_SESSION, APPROVAL_ONLY)
    allow_future = decision == APPROVAL_SESSION and request.session_choice_enabled
    return ApprovalDecision(
        decision=decision,
        allow_current=allow_current,
        allow_future_in_session=allow_future,
        is_delete_operation=request.is_delete_operation,
    )


def build_confirmation_request(tool_name: str, args: dict | None = None) -> ConfirmationRequest:
    args = args or {}
    is_delete_operation = is_delete_operation_request(tool_name, args)
    return ConfirmationRequest(
        tool_name=tool_name,
        args=args,
        is_delete_operation=is_delete_operation,
        session_choice_enabled=not is_delete_operation,
    )


def is_delete_operation_request(tool_name: str, args: dict | None = None) -> bool:
    args = args or {}
    skill_info = None
    try:
        from .tools import registry

        skill_info = registry.get_skill_info(tool_name) or {}
    except Exception:
        skill_info = {}

    action_kind = str(skill_info.get("action_kind") or "").strip().lower()
    if action_kind in {"delete", "destructive_delete"}:
        return True

    if tool_name == "python_eval":
        use_sandbox = args.get("use_sandbox", True)
        if isinstance(use_sandbox, str):
            use_sandbox = use_sandbox.lower() == "true"
        if use_sandbox:
            return False
        code = str(args.get("code") or "")
        for pattern in _DELETE_CODE_PATTERNS:
            if re.search(pattern, code, re.IGNORECASE | re.MULTILINE):
                return True
    if tool_name == "shell_command":
        command = str(args.get("command") or "")
        for pattern in _DELETE_SHELL_PATTERNS:
            if re.search(pattern, command, re.IGNORECASE | re.MULTILINE):
                return True
    return False


def format_approval_status(decision: ApprovalDecision, tool_name: str) -> str | None:
    if decision.source == "session_default":
        return f"当前操作 {tool_name} 已按会话默认同意自动放行。"
    if decision.decision == APPROVAL_SESSION and decision.allow_future_in_session:
        return "已记录为当前会话默认同意；后续非删除类高危操作将自动放行。"
    if decision.decision == APPROVAL_SESSION and not decision.allow_future_in_session:
        return "当前操作已放行，但删除类操作不会开启会话默认同意。"
    if decision.decision == APPROVAL_ONLY:
        return "当前操作已放行，仅本次有效。"
    return None


def format_rejection_message(decision: ApprovalDecision) -> str:
    if decision.decision == APPROVAL_NO:
        return "操作被拒绝：用户选择 no。"
    return f"操作被拒绝：未获授权（decision={decision.decision}）。"


def create_approval_handler(prompt_callback=None, session_id: str | None = None) -> ApprovalHandler:
    return ApprovalHandler(prompt_callback=prompt_callback, session_id=session_id)


def resolve_interaction_handler(interaction_handler, session_id: str | None = None):
    if isinstance(interaction_handler, ApprovalHandler):
        interaction_handler.set_session_id(session_id)
        return interaction_handler
    if interaction_handler:
        return ApprovalHandler(prompt_callback=interaction_handler, session_id=session_id)
    try:
        if sys.stdin and sys.stdin.isatty():
            return ApprovalHandler(
                prompt_callback=_default_cli_interaction_handler,
                session_id=session_id,
            )
    except Exception:
        return None
    return None

