# AwiseOctopus

中文文档 | [English](README.md)

`AwiseOctopus` 是一个基于 Python 的强大智能体系统，采用 **双 Agent 架构（Dual Agent Architecture）**。它协调了负责规划的“思考 Agent（Manager）”和负责调用的“执行 Agent（Worker）”，从而能够自主地分析、规划和执行复杂的用户请求。借助动态注册的工具和灵活的专家技能库，系统实现了高效且精准的任务执行。

## 🌟 愿景

我们的愿景是构建一个具有高度扩展性、自主性和强大容错能力的 Agent 框架，让其开箱即用地解决复杂的多步骤问题。我们希望赋能开发者和最终用户，让 AI 助手不仅能够与本地系统（如极速的 Everything SDK）深度集成，还能在遇到障碍时即时编写 Python 代码并动态调整策略，成为您最可靠的工作伙伴。

## ✨ 核心功能

- **双 Agent 架构**：在 `ThinkingAgent`（负责任务拆解、规划与策略调整）与 `ExecutionAgent`（负责调用工具和实际执行）之间实现了健壮的分工。
- **动态工具注册机制**：基于装饰器 (`@registry.register`) 和 JSON Schema 的自动化工具注册系统。开发者只需极少代码即可轻松扩展执行工具。
- **极速本地搜索**：内置的 `search_local_file` 工具通过 `ctypes` (`Everything64.dll`/`Everything32.dll`) 深度集成了 **Everything SDK**，实现毫秒级的本地文件发现。
- **专家技能（Skill）机制**：灵活的技能加载系统（位于 `skills/` 目录）。Manager 可动态搜索并加载特定领域的 Prompt 或 SOP（如数据分析、前端开发等），指导复杂任务。
- **容错与自动修正**：思考 Agent 会主动评估任务结果。如果常规工具失败，它可以转换策略——比如使用 `python_eval` 工具编写和运行 Python 代码，或者在遇到困境时使用 `ask_user_for_help` 呼叫人类协助。
- **兼容 OpenAI API**：底层基于官方 OpenAI Python SDK，能够完美兼容所有支持 OpenAI API 格式的大语言模型服务。

## 🏗️ 项目架构

1. **ThinkingAgent（思考 Agent / Manager）**：
   - 核心代码：`models/thinking_agent.py`
   - 负责拆解用户的复杂请求、管理整体任务流，并评估执行结果。
   - 通过 `search_skill` 机制动态检索并加载最相关的专家技能。
   - 通过 `execute_subtask` 工具将拆解后的子任务分配给执行 Agent。

2. **ExecutionAgent（执行 Agent / Worker）**：
   - 核心代码：`models/execution_agent.py`
   - 接收 Manager 的指令，根据当前上下文选择并调用可用的工具，精准执行任务。
   - 将客观的执行结果反馈给 Manager。

3. **执行工具库（`models/tools/`）**：
   - `registry.py`：负责工具的管理和调度。
   - `python_eval.py`：安全、动态地执行 Python 代码。
   - `search_local_file.py`：基于 Everything SDK 的极速本地搜索。
   - `web_search.py`：集成搜索引擎功能。
   - `calc.py`：基础计算器。

4. **技能库（`skills/`）**：
   - 存放专家知识库（例如：`data_analysis`、`daily-report-assistant`）。
   - 系统通过匹配文件夹名称、`description.txt` 及 `.md` 文件，动态找到与当前上下文最匹配的技能指南。

## 🚀 快速开始

### 前置要求

- Python 3.10+
- [Everything](https://www.voidtools.com/) 已安装并在后台运行（用于极速本地文件搜索功能）。

### 安装步骤

1. 克隆项目仓库：
   ```bash
   git clone https://github.com/your-username/AwiseOctopus.git
   cd AwiseOctopus
   ```

2. 安装所需依赖：
   ```bash
   pip install -r requirements.txt
   ```

3. 配置环境变量：
   将 `.env.template` 复制为 `.env`，并配置你的 API 密钥：
   ```bash
   cp .env.template .env
   ```
   *编辑 `.env` 文件，填入你的 `api_key`、`base_url` 以及 `MODEL`。*

### 运行系统

推荐通过 `cli_rich` 启动双 Agent 交互式系统：

```bash
python -m cli_rich chat
```

在终端中输入你的需求，观察 Agent 如何协同工作为您解决问题！输入 `exit` 退出系统。

也可以将其安装为命令行工具（可选）：

```bash
pip install -e .
awiseoctopus chat
```

单次执行（适合脚本化调用）：

```bash
python -m cli_rich run --prompt "你好，帮我总结一下今天的工作计划"
```

配置自检（不触发网络/LLM）：

```bash
python -m cli_rich run --dry-run --prompt "hi"
```

旧入口仍保留可用（兼容）：

```bash
python app.py
```

## 🤝 欢迎贡献代码

我们非常欢迎大家来体验 `AwiseOctopus` 并为本项目贡献代码！无论你是想添加新的执行工具、设计强大的专家技能、修复 Bug，还是改进文档，你的贡献对我们都非常重要。

1. Fork 本项目
2. 创建你的特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交你的修改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 提交 Pull Request (PR)

## 📄 开源协议

本项目采用 MIT 开源许可证。
