# Agent API Contract

## Positioning

本契约定义 Flutter 客户端未来接入 Python Agent 服务时的最小接口集合。当前客户端默认使用 Mock API，但 DTO 与事件语义已经固定，不再反复变更。

## Session Endpoints

### `listSessions`

返回会话摘要数组：

```json
[
  {
    "id": "session-001",
    "title": "部署排查",
    "preview": "最近一条回答摘要",
    "lastUpdated": "2026-04-29T10:00:00Z"
  }
]
```

### `createSession`

返回新建会话对象：

```json
{
  "id": "session-002",
  "title": "新会话",
  "preview": "",
  "lastUpdated": "2026-04-29T10:05:00Z"
}
```

### `loadSessionHistory`

返回消息数组：

```json
[
  {
    "id": "m1",
    "role": "user",
    "kind": "text",
    "content": "帮我总结这个需求",
    "createdAt": "2026-04-29T10:05:10Z"
  }
]
```

## Streaming Actions

### `sendPrompt`

请求：

```json
{
  "sessionId": "session-002",
  "prompt": "请规划并执行一个复杂任务"
}
```

### `replyToAskUser`

请求：

```json
{
  "sessionId": "session-002",
  "reply": "目标是 Windows 桌面版"
}
```

### `submitApprovalDecision`

请求：

```json
{
  "sessionId": "session-002",
  "decision": "only"
}
```

## Event Types

所有流式接口都返回如下事件之一：

### `thinking_log`

```json
{
  "type": "thinking_log",
  "text": "=== [思考Agent 启动] 开始分析任务 ==="
}
```

### `ask_user`

```json
{
  "type": "ask_user",
  "text": "请补充你期望的平台范围"
}
```

### `dag_planned`

```json
{
  "type": "dag_planned",
  "tasks": [
    {
      "id": "task-1",
      "instruction": "搜索代码结构",
      "dependencies": []
    }
  ]
}
```

### `dag_status`

```json
{
  "type": "dag_status",
  "dagStatus": {
    "pending": ["task-2"],
    "running": ["task-1"],
    "completed": [],
    "tasks": {
      "task-1": {
        "id": "task-1",
        "instruction": "搜索代码结构",
        "dependencies": []
      }
    }
  }
}
```

### `approval_request`

```json
{
  "type": "approval_request",
  "approvalRequest": {
    "id": "approval-001",
    "tool_name": "shell_command",
    "args": {
      "command": "Remove-Item build -Recurse"
    },
    "is_delete_operation": true,
    "session_choice_enabled": false
  }
}
```

### `dag_result`

```json
{
  "type": "dag_result",
  "rawPayload": {
    "task-1": "搜索完成",
    "task-2": "执行完成"
  }
}
```

### `summary_chunk`

```json
{
  "type": "summary_chunk",
  "text": "正在生成最终总结..."
}
```

### `final_answer`

```json
{
  "type": "final_answer",
  "text": "任务已完成，以下是总结。"
}
```

### `error`

```json
{
  "type": "error",
  "text": "服务暂不可用"
}
```

## Fixed Semantics

- 思考流来源语义固定对齐 Python：`RUNNING` / `ASK_USER` / `FINISHED`
- 审批选项固定为：`session` / `only` / `no`
- 删除类操作必须返回 `session_choice_enabled=false`
- DAG 状态结构固定为：`pending` / `running` / `completed` / `tasks`
