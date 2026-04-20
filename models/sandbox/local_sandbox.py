import io
import contextlib
import traceback

class LocalSandbox:
    """
    A local Python execution environment that mimics a sandbox.
    It preserves state across executions using a shared dictionary for globals.
    
    WARNING: 
    This executes code directly on the host machine using `exec()`. 
    It is NOT a secure sandbox for untrusted code. It is mainly for local testing, 
    rapid development, or scenarios where code execution is fully trusted.
    """

    def __init__(self, **kwargs):
        # We accept kwargs to maintain interface compatibility with OpenAISandbox
        self.model = "local-python-exec"
        self._global_env = {}

    def execute_code(self, code: str) -> str:
        """
        Executes the provided Python code locally and returns the stdout/stderr.
        """
        output = io.StringIO()
        error_output = io.StringIO()
        
        try:
            with contextlib.redirect_stdout(output), contextlib.redirect_stderr(error_output):
                exec(code, self._global_env)
            
            out_str = output.getvalue()
            err_str = error_output.getvalue()
            
            result = ""
            if out_str:
                result += out_str
            if err_str:
                result += f"\n[Error Output]:\n{err_str}"
                
            return result.strip() or "Code executed successfully with no output."
        except Exception:
            return f"Execution failed:\n{traceback.format_exc()}"

    def close(self):
        """
        Cleans up the local execution environment variables.
        """
        self._global_env.clear()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
