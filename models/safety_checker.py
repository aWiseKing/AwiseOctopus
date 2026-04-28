import json
import re


_SHELL_SAFE_PATTERNS = [
    r"^\s*(?:dir|ls|pwd)\s*$",
    r"^\s*(?:echo)\b",
    r"^\s*(?:type|cat|head|tail)\b",
    r"^\s*(?:where|which)\b",
    r"^\s*(?:find)\b",
    r"^\s*git\s+status(?:\s+--short)?\s*$",
    r"^\s*git\s+diff(?:\s+--stat)?(?:\s+--cached)?\s*$",
    r"^\s*git\s+log\b.*$",
    r"^\s*(?:python|python3|py|pip|pip3|node|npm)\s+(?:--version|-V)\s*$",
    r"^\s*(?:pip|pip3)\s+show\b.*$",
    r"^\s*npm\s+list\b.*$",
    r"^\s*Get-(?:ChildItem|Content|Location)\b.*$",
]

_SHELL_UNSAFE_PATTERNS = [
    r"\b(?:rm|rmdir|del|erase)\b",
    r"\bRemove-Item\b",
    r"\b(?:Set-Content|Add-Content|Out-File|Set-ItemProperty|New-Item)\b",
    r"(?<![0-9])>>?",
    r"\b(?:pip|pip3|npm|pnpm|yarn|apt|apt-get|brew|choco)\s+(?:install|uninstall|remove|update|upgrade)\b",
    r"\b(?:curl|wget|Invoke-WebRequest|iwr)\b",
    r"\|\s*(?:sh|bash|pwsh|powershell)\b",
    r"\b(?:taskkill|Stop-Process|kill|pkill|sc|systemctl|setx)\b",
]


def _is_shell_command_safe(args) -> bool | None:
    command = str((args or {}).get("command") or "").strip()
    if not command:
        return False

    for pattern in _SHELL_UNSAFE_PATTERNS:
        if re.search(pattern, command, re.IGNORECASE):
            return False

    for pattern in _SHELL_SAFE_PATTERNS:
        if re.search(pattern, command, re.IGNORECASE):
            return True

    return None

def is_action_safe(client, model, tool_name, args):
    """
    判断工具执行是否安全，是否可以免除人工审查。
    返回 True 表示安全，可免审；False 表示高危，需人工确认。
    """
    # 1. 混合沙箱免审：如果是 python_eval 且 use_sandbox 为 True
    if tool_name == "python_eval":
        use_sandbox = args.get("use_sandbox", True)
        if isinstance(use_sandbox, str):
            use_sandbox = use_sandbox.lower() == 'true'
        if use_sandbox:
            return True

    # 2. Shell 工具的本地快速判定
    if tool_name == "shell_command":
        shell_safe = _is_shell_command_safe(args)
        if shell_safe is not None:
            return shell_safe

    # 3. LLM 动态分析
    prompt = f"""你是一个安全审查专家。请分析以下工具调用是否属于"仅仅获取信息、读取数据或安全的纯计算"，而不包含任何对系统的修改、删除或破坏性操作。

工具名称: {tool_name}
工具参数: {json.dumps(args, ensure_ascii=False, indent=2)}

如果该操作是安全的（如读取文件内容、获取系统状态、执行只读查询、纯逻辑计算等），请回复 "SAFE"。
如果该操作是高危的（如写入文件、删除文件、修改系统配置、执行可能修改状态的脚本、执行未知网络请求等），请回复 "UNSAFE"。
只回复 "SAFE" 或 "UNSAFE"，不要包含任何其他内容。"""

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0
        )
        result = response.choices[0].message.content.strip().upper()
        if "SAFE" in result and "UNSAFE" not in result:
            return True
        elif "UNSAFE" in result:
            return False
        else:
            return False
    except Exception as e:
        print(f"\n    [安全审查] LLM 判断出错: {e}，默认要求人工确认。")
        return False
