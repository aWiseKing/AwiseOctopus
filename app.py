import os
import asyncio
import json
from openai import OpenAI

from models.config_manager import ConfigManager
# 从我们重构后的models包导入Session
from models import Session

# -----------------
# 客户端初始化
# -----------------
config_mgr = ConfigManager()
api_key = config_mgr.get("api_key") or os.getenv("api_key")
base_url = config_mgr.get("base_url") or os.getenv("base_url") or "https://dashscope.aliyuncs.com/compatible-mode/v1"
MODEL = config_mgr.get("MODEL") or os.getenv("MODEL") or "glm-5"

client = OpenAI(
    api_key=api_key,
    base_url=base_url
)

# -----------------
# 交互处理函数
# -----------------
def cli_interaction_handler(tool_name, args):
    print(f"\n[⚠️ 警告] Agent 准备执行高危操作 `{tool_name}`，参数为:")
    print(json.dumps(args, indent=2, ensure_ascii=False))
    user_reply = input("是否允许？(输入 'y' 允许，或者输入修改建议/拒绝原因): ")
    return user_reply

# -----------------
# 主循环
# -----------------
if __name__ == "__main__":
    import shutil
    
    # 终端宽度铺满标题
    terminal_width = shutil.get_terminal_size().columns
    title = " 双Agent架构测试系统 "
    print(title.center(terminal_width, "="))
    
    # 剑盾 ASCII Art
    sword_shield = """
          / \\
        /_____\\
       |       |
  O===[=========]==============-
       |       |
        \\     /
         \\   /
          \\ /
    """
    for line in sword_shield.strip("\n").split("\n"):
        print(line.center(terminal_width))
        
    print()
    print(f"[*] 模型 (MODEL): {MODEL}")
    print(f"[*] 接口 (API)  : {base_url}")
    print("[*] 提示 (HINT) : 输入 'exit' 退出程序，按 Ctrl+C 中断。")
    print("=" * terminal_width)
    
    # 实例化持久的 Session 维持多轮上下文
    session = Session(client, MODEL)
    
    while True:
        try:
            print("\n\033[91m*\033[0m 请输入问题：")
            prompt = input("> ")
            if prompt.strip().lower() == "exit":
                break
            if not prompt.strip():
                continue
            
            final_response = session.think(prompt)
            
            if isinstance(final_response, list):
                print("\n[系统] 接收到 DAG 任务图，开始调度执行...")
                results = asyncio.run(session.execute_dag_async(
                    final_response, 
                    interaction_handler=cli_interaction_handler
                ))
                print(f"\n✅ DAG 最终执行结果（JSON）：\n{json.dumps(results, ensure_ascii=False, indent=2)}\n")
                
                print("\n[系统] 正在生成最终总结报告...\n")
                for chunk in session.summarize_stream(prompt, results):
                    print(chunk, end="", flush=True)
                print("\n")
            else:
                # 使用 encode/decode 避免终端打印生僻字符时报错
                print(f"\n✅ 最终答案：\n{final_response.encode('gbk', 'replace').decode('gbk')}\n")
            
            print("------------------------------------------")
            
        except KeyboardInterrupt:
            print("\n退出...")
            break
        except Exception as e:
            print(f"\n❌ 系统发生错误: {e}")
