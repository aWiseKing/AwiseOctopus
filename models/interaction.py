import json
import sys


def _default_cli_interaction_handler(tool_name: str, args: dict) -> str:
    print(f"\n[⚠️ 警告] Agent 准备执行高危操作 `{tool_name}`，参数为:")
    try:
        print(json.dumps(args, indent=2, ensure_ascii=False))
    except Exception:
        print(str(args))
    user_reply = input("是否允许？(输入 'y' 允许，或者输入修改建议/拒绝原因): ")
    return user_reply


def resolve_interaction_handler(interaction_handler):
    if interaction_handler:
        return interaction_handler
    try:
        if sys.stdin and sys.stdin.isatty():
            return _default_cli_interaction_handler
    except Exception:
        return None
    return None

