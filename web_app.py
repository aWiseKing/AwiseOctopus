import os
import streamlit as st
from openai import OpenAI
from dotenv import load_dotenv

# 从重构后的 models 包导入思考Agent
from models import ThinkingAgent

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
    load_dotenv()
    api_key = os.getenv("api_key")
    base_url = os.getenv("base_url")
    if not api_key:
        st.error("请在 .env 文件中配置 api_key")
        
        st.stop()
    return OpenAI(api_key=api_key, base_url=base_url), os.getenv("MODEL", "gpt-4o")

client, MODEL = get_openai_client()

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
        agent = ThinkingAgent(client, MODEL)
        st.session_state.agent_gen = agent.run_stream(prompt)
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
                        from models import DAGExecutor
                        
                        status_container.info("**任务规划完成，开始调度执行 DAG 图...**")
                        
                        dag_container = st.empty()
                        last_dot_ref = [""]
                        
                        def update_dag(status_data):
                            dot = "digraph DAG {\n"
                            dot += '  node [shape=box, style=filled, fontname="sans-serif"];\n'
                            for tid, t in status_data["tasks"].items():
                                if tid in status_data["completed"]:
                                    color = "lightgreen"
                                elif tid in status_data["running"]:
                                    color = "yellow"
                                else:
                                    color = "lightgrey"
                                
                                # 截取前20个字符作为描述，替换掉双引号以防语法错误
                                instruction_preview = t.get('instruction', '').replace('"', '\\"')[:20]
                                label = f"{tid}\\n{instruction_preview}..."
                                dot += f'  "{tid}" [fillcolor={color}, label="{label}"];\n'
                            
                            for tid, t in status_data["tasks"].items():
                                for dep in t.get("dependencies", []):
                                    dot += f'  "{dep}" -> "{tid}";\n'
                            dot += "}\n"
                            last_dot_ref[0] = dot
                            dag_container.graphviz_chart(dot)

                        # 初始化并执行 DAG
                        executor = DAGExecutor(payload, client, MODEL, agent, on_status_change=update_dag)
                        results = asyncio.run(executor.execute())
                        
                        status_container.success("**DAG 任务全部执行完成！**")
                        final_res_str = json.dumps(results, ensure_ascii=False, indent=2)
                        
                        # 展示执行结果的 JSON
                        with st.expander("DAG 执行结果 (JSON 详情)", expanded=False):
                            st.code(final_res_str, language="json")
                            
                        # 保存到 session_state 以便历史记录渲染
                        st.session_state.messages.append({
                            "role": "assistant", 
                            "type": "dag_result", 
                            "content": final_res_str, 
                            "dot": last_dot_ref[0]
                        })
                        
                        status_container.info("**正在生成最终总结报告...**")
                        summary_container = st.empty()
                        summary_text = ""
                        # prompt为最开始的用户输入（在上方由st.chat_input获取）
                        for chunk in agent.summarize_dag_results_stream(prompt, results):
                            summary_text += chunk
                            summary_container.markdown(summary_text)
                            
                        status_container.success("**所有任务已完成！**")
                        st.session_state.messages.append({
                            "role": "assistant", 
                            "type": "final", 
                            "content": summary_text
                        })
                    else:
                        status_container.success(f"**最终答案:**\n\n{payload}")
                        st.session_state.messages.append({"role": "assistant", "type": "final", "content": payload})
                    
                    # 清理状态
                    st.session_state.agent_gen = None
                    break
                    
        except StopIteration as e:
            # 正常情况下生成器会在 FINISHED 状态返回，如果意外结束也清理状态
            st.session_state.agent_gen = None
