import os
import streamlit as st
from openai import OpenAI
from models.config_manager import ConfigManager
from models.interaction import create_approval_handler

# 从重构后的 models 包导入Session
from models import Session

# -----------------
# 页面配置与样式
# -----------------
st.set_page_config(page_title="AwiseOctopus", page_icon="🤖", layout="wide")

st.title("🤖 AwiseOctopus")
st.markdown("hello world")

# -----------------
# 客户端初始化
# -----------------
@st.cache_resource
def get_openai_client():
    config_mgr = ConfigManager()
    api_key = config_mgr.get("api_key") or os.getenv("api_key")
    base_url = config_mgr.get("base_url") or os.getenv("base_url") or "https://dashscope.aliyuncs.com/compatible-mode/v1"
    MODEL = config_mgr.get("MODEL") or os.getenv("MODEL") or "gpt-4o"
    if not api_key:
        st.error("请使用 cli_rich env set api_key <your_key> 配置 api_key")
        
        st.stop()
    return OpenAI(api_key=api_key, base_url=base_url), MODEL

client, MODEL = get_openai_client()


def web_interaction_handler(request):
    import threading

    req = {
        "tool_name": request["tool_name"],
        "args": request["args"],
        "is_delete_operation": request["is_delete_operation"],
        "session_choice_enabled": request["session_choice_enabled"],
        "event": threading.Event(),
        "response": None,
    }
    st.session_state.interaction_requests.append(req)
    req["event"].wait()
    return req["response"]

# -----------------
# Session State 初始化
# -----------------
if "messages" not in st.session_state:
    # 用于存储聊天记录
    st.session_state.messages = []

if "agent_gen" not in st.session_state:
    # 存储当前活跃的生成器
    st.session_state.agent_gen = None

if "logs" not in st.session_state:
    # 存储当前任务的中间日志
    st.session_state.logs = []

if "interaction_requests" not in st.session_state:
    st.session_state.interaction_requests = []

if "dag_running" not in st.session_state:
    st.session_state.dag_running = False

if "dag_results" not in st.session_state:
    st.session_state.dag_results = None

if "dag_status_data" not in st.session_state:
    st.session_state.dag_status_data = None

if "dag_prompt" not in st.session_state:
    st.session_state.dag_prompt = None

if "summary_text" not in st.session_state:
    st.session_state.summary_text = ""

if "summary_generator" not in st.session_state:
    st.session_state.summary_generator = None

if "approval_handler" not in st.session_state:
    st.session_state.approval_handler = create_approval_handler(
        web_interaction_handler
    )

if "session" not in st.session_state:
    # 实例化持久的 Session 维持多轮上下文
    st.session_state.session = Session(
        client,
        MODEL,
        interaction_handler=st.session_state.approval_handler,
    )
else:
    st.session_state.session.interaction_handler = st.session_state.approval_handler
    st.session_state.session.agent.interaction_handler = st.session_state.approval_handler

# -----------------
# 渲染历史消息
# -----------------
for msg in st.session_state.messages:
    if msg["role"] == "user":
        with st.chat_message("user"):
            st.markdown(msg["content"])
    elif msg["role"] == "assistant":
        with st.chat_message("assistant"):
            if msg.get("type") == "logs":
                with st.expander("Agent 执行日志", expanded=False):
                    st.code(msg["content"], language="text")
            elif msg.get("type") == "ask":
                st.warning(f"**Agent 求助:**\n\n{msg['content']}")
            elif msg.get("type") == "final":
                st.success(f"**最终答案:**\n\n{msg['content']}")
            elif msg.get("type") == "dag_result":
                if "dot" in msg:
                    st.graphviz_chart(msg["dot"])
                with st.expander("DAG 执行结果", expanded=True):
                    # content is a json string
                    st.code(msg["content"], language="json")

# -----------------
# 聊天输入与逻辑处理
# -----------------
if prompt := st.chat_input("Please enter a question or reply to the agent's request for assistance ..."):
    # 展示用户输入
    with st.chat_message("user"):
        st.markdown(prompt)
    st.session_state.messages.append({"role": "user", "content": prompt})
    
    user_input_to_send = None
    
    # 判断是新任务还是回复 Agent 求助
    if st.session_state.agent_gen is None:
        st.session_state.agent_gen = st.session_state.session.think_stream(prompt)
        st.session_state.logs = []
    else:
        user_input_to_send = prompt

    # 准备渲染本次 Agent 的执行过程
    with st.chat_message("assistant"):
        log_expander = st.expander("Agent 执行日志", expanded=True)
        log_container = log_expander.empty()
        
        status_container = st.empty()
        
        try:
            # 步进生成器
            if user_input_to_send is not None:
                status, payload = st.session_state.agent_gen.send(user_input_to_send)
            else:
                status, payload = next(st.session_state.agent_gen)
                
            # 持续消费 RUNNING 状态，直到遇到 ASK_USER 或 FINISHED
            while True:
                if status == "RUNNING":
                    st.session_state.logs.append(payload)
                    log_container.code("\n".join(st.session_state.logs), language="text")
                    # 继续获取下一步
                    status, payload = next(st.session_state.agent_gen)
                    
                elif status == "ASK_USER":
                    # Agent 需要求助，挂起生成器，等待下一次用户输入
                    st.session_state.messages.append({"role": "assistant", "type": "logs", "content": "\n".join(st.session_state.logs)})
                    st.session_state.logs = [] # 清空日志为下一次做准备
                    
                    status_container.warning(f"**Agent 求助:**\n\n{payload}")
                    st.session_state.messages.append({"role": "assistant", "type": "ask", "content": payload})
                    break
                    
                elif status == "FINISHED":
                    # 任务完成
                    st.session_state.messages.append({"role": "assistant", "type": "logs", "content": "\n".join(st.session_state.logs)})
                    st.session_state.logs = []
                    
                    if isinstance(payload, list):
                        import json
                        import asyncio
                        import threading
                        
                        status_container.info("**任务规划完成，开始调度执行 DAG 图...**")
                        
                        st.session_state.dag_running = True
                        st.session_state.dag_results = None
                        st.session_state.dag_prompt = prompt
                        
                        def update_dag(status_data):
                            st.session_state.dag_status_data = status_data

                        def run_dag_thread(session_obj, app_session):
                            # The executor runs in a new event loop
                            try:
                                loop = asyncio.new_event_loop()
                                asyncio.set_event_loop(loop)
                                results = loop.run_until_complete(session_obj.execute_dag_async(
                                    payload,
                                    on_status_change=update_dag,
                                    interaction_handler=app_session.approval_handler
                                ))
                                app_session.dag_results = results
                            except Exception as e:
                                app_session.dag_results = f"DAG执行错误: {e}"
                            finally:
                                app_session.dag_running = False

                        t = threading.Thread(target=run_dag_thread, args=(st.session_state.session, st.session_state))
                        t.daemon = True
                        t.start()
                        
                        # 清理状态并触发 rerender 以显示 DAG 状态
                        st.session_state.agent_gen = None
                        st.rerun()
                    else:
                        status_container.success(f"**最终答案:**\n\n{payload}")
                        st.session_state.messages.append({"role": "assistant", "type": "final", "content": payload})
                        st.session_state.agent_gen = None
                        break
                    
        except StopIteration as e:
            # 正常情况下生成器会在 FINISHED 状态返回，如果意外结束也清理状态
            st.session_state.agent_gen = None

# -----------------
# 渲染后台 DAG 执行状态与交互
# -----------------
if st.session_state.dag_running or st.session_state.dag_results is not None:
    # 渲染图表
    if st.session_state.dag_status_data:
        status_data = st.session_state.dag_status_data
        dot = "digraph DAG {\n"
        dot += '  node [shape=box, style=filled, fontname="sans-serif"];\n'
        for tid, t in status_data["tasks"].items():
            if tid in status_data["completed"]:
                color = "lightgreen"
            elif tid in status_data["running"]:
                color = "yellow"
            else:
                color = "lightgrey"
            instruction_preview = t.get('instruction', '').replace('"', '\\"')[:20]
            label = f"{tid}\\n{instruction_preview}..."
            dot += f'  "{tid}" [fillcolor={color}, label="{label}"];\n'
        
        for tid, t in status_data["tasks"].items():
            for dep in t.get("dependencies", []):
                dot += f'  "{dep}" -> "{tid}";\n'
        dot += "}\n"
        st.graphviz_chart(dot)

    # 处理交互请求
    if st.session_state.interaction_requests:
        req = st.session_state.interaction_requests[0] # 取出第一个请求
        st.warning(f"**Agent 请求确认高危操作:** `{req['tool_name']}`")
        st.json(req['args'])
        if req["is_delete_operation"]:
            st.info("这是删除类操作。即使选择 `session`，也只会同意当前这一次，不会开启本对话默认同意。")
        else:
            st.info("选择 `session` 后，本对话后续非删除类高危操作将默认同意。")
        
        with st.form(key=f"confirm_form_{id(req)}"):
            user_decision = st.selectbox(
                "请选择授权方式",
                options=["session", "only", "no"],
                index=2,
            )
            submitted = st.form_submit_button("提交决定")
            if submitted:
                req["response"] = user_decision
                st.session_state.interaction_requests.pop(0)
                req["event"].set()
                st.rerun()

    elif st.session_state.dag_running:
        # 如果没有交互请求，并且还在运行，显示刷新按钮或自动刷新
        import time
        st.info("DAG 任务后台执行中...")
        time.sleep(1.5)
        st.rerun()

    # 处理 DAG 执行完成
    if not st.session_state.dag_running and st.session_state.dag_results is not None and not st.session_state.summary_generator:
        import json
        st.success("**DAG 任务全部执行完成！**")
        final_res_str = json.dumps(st.session_state.dag_results, ensure_ascii=False, indent=2)
        with st.expander("DAG 执行结果 (JSON 详情)", expanded=False):
            st.code(final_res_str, language="json")
        
        # 存入消息历史
        dot_str = ""
        if st.session_state.dag_status_data:
            # 重新生成 dot 存入历史
            status_data = st.session_state.dag_status_data
            dot_str = "digraph DAG {\n"
            dot_str += '  node [shape=box, style=filled, fontname="sans-serif"];\n'
            for tid, t in status_data["tasks"].items():
                if tid in status_data["completed"]:
                    color = "lightgreen"
                elif tid in status_data["running"]:
                    color = "yellow"
                else:
                    color = "lightgrey"
                instruction_preview = t.get('instruction', '').replace('"', '\\"')[:20]
                label = f"{tid}\\n{instruction_preview}..."
                dot_str += f'  "{tid}" [fillcolor={color}, label="{label}"];\n'
            for tid, t in status_data["tasks"].items():
                for dep in t.get("dependencies", []):
                    dot_str += f'  "{dep}" -> "{tid}";\n'
            dot_str += "}\n"
            
        st.session_state.messages.append({
            "role": "assistant", 
            "type": "dag_result", 
            "content": final_res_str, 
            "dot": dot_str
        })
        
        # 准备生成总结
        st.session_state.summary_generator = st.session_state.session.summarize_stream(st.session_state.dag_prompt, st.session_state.dag_results)
        st.session_state.summary_text = ""
        st.rerun()

    # 处理总结流式输出
    if st.session_state.summary_generator is not None:
        st.info("**正在生成最终总结报告...**")
        try:
            chunk = next(st.session_state.summary_generator)
            st.session_state.summary_text += chunk
            st.markdown(st.session_state.summary_text)
            import time
            time.sleep(0.1)
            st.rerun()
        except StopIteration:
            st.success("**所有任务已完成！**")
            st.session_state.messages.append({
                "role": "assistant", 
                "type": "final", 
                "content": st.session_state.summary_text
            })
            st.session_state.summary_generator = None
            st.session_state.dag_results = None # 清理状态，表示本次流程完全结束
            st.rerun()
