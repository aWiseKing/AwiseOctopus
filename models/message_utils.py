def normalize_assistant_message(message):
    """Return an API-ready assistant message dict without dropping provider fields."""
    if isinstance(message, dict):
        return message

    model_dump = getattr(message, "model_dump", None)
    if callable(model_dump):
        data = model_dump(exclude_none=True)
        if isinstance(data, dict):
            data.setdefault("role", getattr(message, "role", None) or "assistant")
            return data

    role = getattr(message, "role", None) or "assistant"
    content = getattr(message, "content", None)
    tool_calls = getattr(message, "tool_calls", None)

    normalized = {"role": role, "content": content}

    reasoning_content = getattr(message, "reasoning_content", None)
    if reasoning_content is not None:
        normalized["reasoning_content"] = reasoning_content

    model_extra = getattr(message, "model_extra", None)
    if isinstance(model_extra, dict):
        reasoning_content = model_extra.get("reasoning_content")
        if reasoning_content is not None:
            normalized["reasoning_content"] = reasoning_content

    if tool_calls:
        calls = []
        for tool_call in tool_calls:
            tool_call_dump = getattr(tool_call, "model_dump", None)
            if callable(tool_call_dump):
                dumped = tool_call_dump(exclude_none=True)
                if isinstance(dumped, dict):
                    calls.append(dumped)
                    continue

            function = getattr(tool_call, "function", None)
            calls.append(
                {
                    "id": getattr(tool_call, "id", None),
                    "type": getattr(tool_call, "type", "function"),
                    "function": {
                        "name": getattr(function, "name", None),
                        "arguments": getattr(function, "arguments", None),
                    },
                }
            )
        normalized["tool_calls"] = calls

    return normalized


def model_requires_reasoning_content(model) -> bool:
    return "deepseek" in str(model or "").lower()


def messages_for_model(messages, model):
    if not model_requires_reasoning_content(model):
        return messages

    prepared = []
    for message in messages:
        if (
            isinstance(message, dict)
            and message.get("role") == "assistant"
            and "reasoning_content" not in message
        ):
            message = {**message, "reasoning_content": ""}
        prepared.append(message)
    return prepared
