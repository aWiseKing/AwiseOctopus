# Web UI for Awise Agent (Streamlit)

## 1. 目标与概述
为当前的 `awise_agent` 命令行程序开发一个基于 Streamlit 的 Web 可视化界面。
支持实时展示 Agent 的工具调用日志与思考过程，并支持在 Web 界面中处理 Agent 遇到困难时向用户发起的求助 (`ask_user_for_help`)。
在重构过程中，将保证原有的命令行入口 (`app.py`) 仍然可以正常运行。

## 2. 现状分析
- 目前 `ThinkingAgent` 和 `ExecutionAgent` 的 `run` 方法都是阻塞式的，且在执行过程中直接调用 `print` 打印日志，以及使用 `input()` 来获取用户帮助。
- 这种硬编码的标准输入输出方式无法直接集成到 Web 框架（如 Streamlit）中，因为 Streamlit 是基于无状态的重新运行机制。

## 3. 改造方案

### 3.1 重构执行 Agent (`models/execution_agent.py`)
- **新增 `run_stream(self, instruction)` 方法**：
  将原本的 `print` 替换为 `yield`，使执行过程变成一个生成器。每次工具调用或收到结果时，通过 `yield` 返回中间日志。
- **保留并修改 `run(self, instruction)` 方法**：
  使原 `run` 方法成为 `run_stream` 的包装器，在内部通过 `for log in self.run_stream(instruction): print(log)` 消费生成器，保持向后兼容。

### 3.2 重构思考 Agent (`models/thinking_agent.py`)
- **新增 `run_stream(self, user_request)` 方法**：
  同样采用生成器模式：
  - 遇到普通日志或 `ExecutionAgent` 的日志时，`yield ("RUNNING", log_msg)`。
  - 遇到 `ask_user_for_help` 时，通过 `user_reply = yield ("ASK_USER", question)` 挂起生成器，等待外部传入用户的回答。
  - 任务结束时，`yield ("FINISHED", final_answer)`。
- **保留并修改 `run(self, user_request)` 方法**：
  包装 `run_stream`，遇到 `ASK_USER` 时调用 `input()` 并将结果通过 `.send(user_reply)` 发回生成器，保持原 CLI 体验完全不变。

### 3.3 开发 Streamlit Web 页面 (`web_app.py`)
- **新建文件 `web_app.py`**：
  - 加载环境变量并初始化 OpenAI 客户端。
  - 使用 `st.session_state` 管理聊天历史 (`messages`) 和当前活跃的 Agent 生成器 (`agent_gen`)。
  - 使用 `st.chat_message` 和 `st.chat_input` 构建类似 ChatGPT 的对话界面。
  - 核心逻辑：
    - 如果当前有挂起的生成器 (`agent_gen` 存在)，则将用户输入通过 `send()` 传给生成器，让 Agent 恢复执行。
    - 如果没有挂起的生成器，则用新的用户输入创建并启动一个新的 Agent 生成器。
    - 使用循环消费生成器产出的中间状态，使用 `st.empty()` 或 `st.status()` 实时刷新日志。
    - 如果生成器返回 `ASK_USER`，则退出循环，等待用户在下一次 `st.chat_input` 中输入。
    - 如果生成器返回 `FINISHED`，则展示最终结果并清空当前生成器状态。

### 3.4 依赖管理 (`requirements.txt`)
- 创建或更新 `requirements.txt` 文件，加入必要的依赖：`openai`, `python-dotenv`, `streamlit`。

## 4. 假设与决策
- **选择 Streamlit**：开发效率高，且其 `chat_message` 等组件非常适合构建 Agent 对话流。
- **使用生成器 (Generators)**：相较于多线程和队列，Python 的生成器可以非常优雅地实现函数的挂起和恢复，且不依赖任何外部框架，这使得核心 Agent 代码依然保持纯粹的 Python 逻辑。
- **向后兼容**：不破坏 `app.py` 的执行，确保其他模块或老用户仍然可以通过命令行使用。

## 5. 验证步骤
1. 安装依赖：`pip install -r requirements.txt` (确保已安装 streamlit)。
2. CLI 验证：运行 `python app.py`，确认命令行版本功能正常。
3. Web 验证：运行 `streamlit run web_app.py`。
4. 功能测试：
   - 输入一个简单任务，观察日志是否实时流式输出。
   - 触发一个需要求助的任务，检查 Agent 是否会在 Web 页面暂停并等待输入，且输入后能否正常恢复执行并最终完成任务。