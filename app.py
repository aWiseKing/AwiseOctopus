import os
import asyncio
import json
from openai import OpenAI
from dotenv import load_dotenv
load_dotenv()

# 从我们重构后的models包导入思考Agent和DAGExecutor
from models import ThinkingAgent, DAGExecutor

# -----------------
# 客户端初始化
# -----------------
api_key = os.getenv("api_key")
base_url = os.getenv("base_url")
MODEL = os.getenv("MODEL")

client = OpenAI(
    api_key=api_key,
    base_url=base_url
)

# -----------------
# 主循环
# -----------------
if __name__ == "__main__":
    print("------------------------------------------")
    print("双Agent架构测试系统已启动")
    print("输入 'exit' 退出。")
    print("------------------------------------------")
    
    while True:
        try:
            prompt = input("\n请输入问题：")
            if prompt.strip().lower() == "exit":
                break
            if not prompt.strip():
                continue
            
            manager = ThinkingAgent(client, MODEL)
            final_response = manager.run(prompt)
            
            if isinstance(final_response, list):
                print("\n[系统] 接收到 DAG 任务图，开始调度执行...")
                executor = DAGExecutor(final_response, client, MODEL, manager)
                results = asyncio.run(executor.execute())
                print(f"\n✅ DAG 最终执行结果（JSON）：\n{json.dumps(results, ensure_ascii=False, indent=2)}\n")
                
                print("\n[系统] 正在生成最终总结报告...\n")
                for chunk in manager.summarize_dag_results_stream(prompt, results):
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
