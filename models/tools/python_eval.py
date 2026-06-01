import traceback
from .registry import registry
from models.sandbox.ao_local_sandbox import AOLocalSandbox

# 初始化全局沙箱单例，复用上下文状态
_sandbox_instance = None
_local_instance = None

def get_sandbox(use_sandbox=True):
    if use_sandbox:
        global _sandbox_instance
        if _sandbox_instance is None:
            # 默认带沙箱
            _sandbox_instance = AOLocalSandbox()
        return _sandbox_instance
    else:
        global _local_instance
        if _local_instance is None:
            # 不使用沙箱，在宿主机原生子进程运行
            _local_instance = AOLocalSandbox(use_docker=False)
        return _local_instance

@registry.register(
    name="python_eval",
    description="执行一段Python代码并获取标准输出。对于需要直接操作PC的行为（设置 use_sandbox=False），你必须先编写一段使用虚拟数据的测试代码，在沙箱中（use_sandbox=True）运行以验证核心逻辑和语法。测试通过后，才能使用 use_sandbox=False 执行真实的PC操作代码。",
    parameters={
        "type": "object",
        "properties": {
            "code": {"type": "string", "description": "要执行的Python代码字符串"},
            "use_sandbox": {"type": "boolean", "description": "是否在沙箱中执行。默认为True。当需要直接操作用户宿主机（如读写本地文件、修改系统配置）时，请设置为False。"}
        },
        "required": ["code"]
    },
    requires_confirmation=True,
    action_kind="code_execution",
)
def python_eval(code, use_sandbox=True):
    mode_str = "沙箱模式(Docker)" if use_sandbox else "宿主机实操模式(原生PC)"
    print(f"\n    [系统提示] 执行Agent正在使用 {mode_str} 执行Python代码: \n{code}")
    try:
        sandbox = get_sandbox(use_sandbox=use_sandbox)
        result = sandbox.execute_code(code)
        return result
    except Exception:
        return f"代码执行发生异常:\n{traceback.format_exc()}"
