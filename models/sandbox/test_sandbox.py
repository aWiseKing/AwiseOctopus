import os
import sys
from dotenv import load_dotenv

# 加载 .env 文件中的环境变量
load_dotenv()

# 将父目录加入系统路径，确保可以直接运行此脚本测试
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from models.sandbox.openai_sandbox import OpenAISandbox
from models.sandbox.local_sandbox import LocalSandbox

def run_tests(sandbox):
    print(f"--- Running tests for Sandbox: {sandbox.__class__.__name__} ---")
    # 1. 测试简单的代码输出
    print("--- Test 1: Simple Print ---")
    code_print = "print('Hello Sandbox!')"
    print(f"Code to execute:\n{code_print}\n")
    result_print = sandbox.execute_code(code_print)
    print(f"Result:\n{result_print}\n")

    # 2. 测试状态保留
    print("--- Test 2: State Persistence ---")
    code_def = "x = 42\nprint('Variable x defined.')"
    print(f"Code to execute:\n{code_def}\n")
    result_def = sandbox.execute_code(code_def)
    print(f"Result:\n{result_def}\n")

    code_use = "print(f'The value of x is {x}')"
    print(f"Code to execute:\n{code_use}\n")
    result_use = sandbox.execute_code(code_use)
    print(f"Result:\n{result_use}\n")

    # 3. 测试错误处理
    print("--- Test 3: Error Handling ---")
    code_err = "1 / 0"
    print(f"Code to execute:\n{code_err}\n")
    result_err = sandbox.execute_code(code_err)
    print(f"Result:\n{result_err}\n")
    print("-" * 50 + "\n")

def main():
    print("Initializing Sandboxes...\n")
    
    # ---------------- 测试 LocalSandbox ----------------
    try:
        with LocalSandbox() as local_sandbox:
            print(f"LocalSandbox initialized successfully with model: {local_sandbox.model}\n")
            run_tests(local_sandbox)
    except Exception as e:
        print(f"LocalSandbox test failed: {e}")

    # ---------------- 测试 OpenAISandbox ----------------
    try:
        with OpenAISandbox() as openai_sandbox:
            print(f"OpenAISandbox initialized successfully with model: {openai_sandbox.model}\n")
            run_tests(openai_sandbox)

    except Exception as e:
        if "404" in str(e):
            print(f"Sandbox test failed with 404: {e}\n"
                  f"Note: The current BASE_URL ({os.environ.get('base_url')}) might not support OpenAI's Assistants API (e.g., /v1/assistants endpoint). "
                  f"Please use an OpenAI-compatible API that supports the 'code_interpreter' tool.")
        else:
            print(f"Sandbox test failed: {e}")

if __name__ == "__main__":
    main()
