# AwiseOctopus

[中文文档](README_zh.md) | English

`AwiseOctopus` is a powerful Python-based intelligent agent system utilizing a **Dual Agent Architecture**. It coordinates a Thinking Agent (Manager) and an Execution Agent (Worker) to autonomously analyze, plan, and execute complex user requests. By leveraging dynamic tools and expert skills, the system achieves highly efficient and precise task execution.

## 🌟 Vision

Our vision is to build an autonomous, highly extensible, and fault-tolerant agent framework capable of solving complex multi-step problems out of the box. We aim to empower developers and end-users with an AI assistant that can seamlessly integrate local systems (like the ultra-fast Everything SDK), execute Python code on the fly, and dynamically adapt its strategies when encountering roadblocks.

## ✨ Key Features

- **Dual Agent Architecture**: A robust division of labor between the `ThinkingAgent` (task breakdown, planning, strategy adjustment) and the `ExecutionAgent` (tool invocation, practical execution).
- **Dynamic Tool Registry**: A decorator-based automatic tool registration system (`@registry.register`) using JSON Schema. Tools can be easily extended and discovered by the Execution Agent.
- **Ultra-Fast Local Search**: Built-in `search_local_file` tool integrating the **Everything SDK** via `ctypes` (`Everything64.dll`/`Everything32.dll`), enabling instantaneous local file discovery.
- **Expert Skill Mechanism**: A flexible skill loading system located in the `skills/` directory. The Manager can dynamically search and load domain-specific Prompts or SOPs (Standard Operating Procedures) to guide complex tasks like data analysis or coding.
- **Fault-Tolerance & Auto-Correction**: The Manager actively monitors task outcomes. If standard tools fail, it can pivot strategies—such as writing and executing Python code via the `python_eval` tool—or fallback to `ask_user_for_help` for human intervention.
- **OpenAI Compatible API**: Built on the official OpenAI Python SDK, making it compatible with any LLM service that supports the OpenAI API format.

## 🏗️ Architecture

1. **ThinkingAgent (Manager)**:
   - Resides in `models/thinking_agent.py`.
   - Responsible for breaking down complex requests, managing the overall task workflow, and evaluating execution results.
   - Loads relevant expert skills dynamically using the `search_skill` mechanism.
   - Delegates subtasks to the Worker via the `execute_subtask` tool.

2. **ExecutionAgent (Worker)**:
   - Resides in `models/execution_agent.py`.
   - Receives instructions from the Manager and executes them precisely using available tools.
   - Returns factual execution results back to the Manager.

3. **Execution Tools (`models/tools/`)**:
   - `registry.py`: The core registry for tool management.
   - `python_eval.py`: Safely evaluates and executes Python code dynamically.
   - `search_local_file.py`: High-speed local search powered by Everything SDK.
   - `web_search.py`: Integrates search engine capabilities.
   - `calc.py`: Basic calculator functionalities.

4. **Skills (`skills/`)**:
   - Contains expert knowledge bases (e.g., `data_analysis`, `daily-report-assistant`).
   - The system searches folder names, `description.txt`, and `.md` files to find the best-matching skill guidelines for the current context.

## 🚀 Getting Started

### Prerequisites

- Python 3.10+
- [Everything](https://www.voidtools.com/) installed and running (for local file search capabilities).

### Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/your-username/awise_agent.git
   cd awise_agent
   ```

2. Install the required dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Configure environment variables:
   Copy `.env.template` to `.env` and configure your API credentials:
   ```bash
   cp .env.template .env
   ```
   *Edit `.env` to add your `api_key`, `base_url`, and `MODEL`.*

### Running the System

Recommended: start the dual agent interactive system via `cli_rich`:

```bash
python -m cli_rich chat
```

Type your request in the terminal and watch the agents collaborate to solve it! Type `exit` to quit.

Optional: install as a CLI command:

```bash
pip install -e .
awiseoctopus chat
```

One-shot execution (good for scripting):

```bash
python -m cli_rich run --prompt "Hello, summarize my tasks for today"
```

Config check (no network/LLM calls):

```bash
python -m cli_rich run --dry-run --prompt "hi"
```

Legacy entrypoint is still available (compat):

```bash
python app.py
```

## 🤝 Contributing

We welcome everyone to experience `awise_agent` and contribute to its codebase! Whether you want to add new execution tools, design powerful expert skills, fix bugs, or improve documentation, your contributions are highly valued.

1. Fork the Project
2. Create your Feature Branch (`git checkout -b feature/AmazingFeature`)
3. Commit your Changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the Branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## 📄 License

This project is licensed under the MIT License.
