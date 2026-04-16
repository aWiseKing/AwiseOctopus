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

# -----------------
# 聊天输入与逻辑处理
# -----------------
if prompt := st.chat_input("请输入问题或回复 Agent 的求助..."):
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
                    
                    status_container.success(f"**最终答案:**\n\n{payload}")
                    st.session_state.messages.append({"role": "assistant", "type": "final", "content": payload})
                    
                    # 清理状态
                    st.session_state.agent_gen = None
                    break
                    
        except StopIteration as e:
            # 正常情况下生成器会在 FINISHED 状态返回，如果意外结束也清理状态
            st.session_state.agent_gen = None
