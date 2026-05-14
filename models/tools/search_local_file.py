import sys
import ctypes
import threading
from .registry import registry
from ..runtime_paths import resource_path

# 全局变量缓存 Everything SDK 库
_everything_dll = None
_dll_load_error = None
_everything_lock = threading.Lock()


def _everything_dll_path() -> str:
    if sys.maxsize > 2**32:
        return str(resource_path("libs", "Everything_SDK", "dll", "Everything64.dll"))
    return str(resource_path("libs", "Everything_SDK", "dll", "Everything32.dll"))


def _load_everything_dll():
    global _everything_dll, _dll_load_error
    if _everything_dll is not None:
        return _everything_dll

    try:
        # 获取 dll 路径
        dll_path = _everything_dll_path()
            
        if not os.path.exists(dll_path):
            _dll_load_error = f"未找到 Everything SDK 库文件: {dll_path}"
            return None

        # 加载 DLL
        dll = ctypes.WinDLL(dll_path)
        
        # 配置函数参数和返回值类型
        dll.Everything_SetSearchW.argtypes = [ctypes.c_wchar_p]
        dll.Everything_SetSearchW.restype = None
        
        dll.Everything_SetMax.argtypes = [ctypes.c_uint32]
        dll.Everything_SetMax.restype = None
        
        dll.Everything_QueryW.argtypes = [ctypes.c_int]
        dll.Everything_QueryW.restype = ctypes.c_int
        
        dll.Everything_GetNumResults.argtypes = []
        dll.Everything_GetNumResults.restype = ctypes.c_int
        
        dll.Everything_GetResultFullPathNameW.argtypes = [ctypes.c_uint32, ctypes.c_wchar_p, ctypes.c_uint32]
        dll.Everything_GetResultFullPathNameW.restype = ctypes.c_uint32
        
        dll.Everything_GetLastError.argtypes = []
        dll.Everything_GetLastError.restype = ctypes.c_uint32
        
        _everything_dll = dll
        return _everything_dll
    except Exception as e:
        _dll_load_error = f"加载 Everything SDK 失败: {e}"
        return None

@registry.register(
    name="search_local_file",
    description="使用 Everything 搜索引擎在本地计算机上极速查找文件和目录",
    parameters={
        "type": "object",
        "properties": {
            "keyword": {
                "type": "string", 
                "description": "搜索关键词，支持 Everything 的高级搜索语法（如通配符、正则等）。例如 'Everything64.dll' 或 'ext:md'"
            },
            "max_results": {
                "type": "integer",
                "description": "最大返回结果数量。默认为 10，如果文件可能很多，可以调大但建议不超过 50。"
            }
        },
        "required": ["keyword"]
    }
)
def search_local_file(keyword, max_results=10):
    dll = _load_everything_dll()
    if not dll:
        return _dll_load_error

    try:
        # 使用锁确保对 DLL 全局状态的修改是线程安全的
        with _everything_lock:
            # 1. 设置搜索词
            dll.Everything_SetSearchW(keyword)
            
            # 2. 设置最大返回数
            dll.Everything_SetMax(int(max_results))
            
            # 3. 执行同步查询
            # 参数 1 表示 bWait=True (等待查询完成)
            success = dll.Everything_QueryW(1)
            if not success:
                err_code = dll.Everything_GetLastError()
                if err_code == 2: # EVERYTHING_ERROR_IPC
                    return "Everything 搜索失败: Everything 客户端未运行。请确保本地已启动 Everything 软件。"
                return f"Everything 搜索失败，错误代码: {err_code}"
                
            # 4. 获取结果数量
            num_results = dll.Everything_GetNumResults()
            if num_results == 0:
                return f"未找到与 '{keyword}' 匹配的文件或目录。"
                
            # 5. 遍历并获取结果路径
            results = []
            # Windows MAX_PATH 通常为 260，但为了支持长路径使用 32768
            buf = ctypes.create_unicode_buffer(32768)
            
            for i in range(num_results):
                dll.Everything_GetResultFullPathNameW(i, buf, len(buf))
                results.append(buf.value)
                
        # 6. 格式化输出
        output = f"找到 {num_results} 个匹配项 (限制最多显示 {max_results} 个):\n"
        for idx, path in enumerate(results, 1):
            output += f"{idx}. {path}\n"
            
        return output

    except Exception as e:
        return f"使用 Everything 搜索时发生异常: {str(e)}"
