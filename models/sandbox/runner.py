import sys
import io
import contextlib
import traceback
import base64

global_env = {}

def main():
    while True:
        try:
            line = sys.stdin.readline()
        except EOFError:
            break
            
        if not line:
            break
            
        line = line.strip()
        if not line:
            continue
            
        try:
            code = base64.b64decode(line).decode('utf-8')
        except Exception as e:
            err_msg = f"Decode error: {e}"
            sys.stdout.write(base64.b64encode(err_msg.encode('utf-8')).decode('utf-8') + "\n")
            sys.stdout.flush()
            continue

        output = io.StringIO()
        error_output = io.StringIO()
        
        try:
            with contextlib.redirect_stdout(output), contextlib.redirect_stderr(error_output):
                exec(code, global_env)
            
            out_str = output.getvalue()
            err_str = error_output.getvalue()
            
            result = ""
            if out_str: result += out_str
            if err_str: result += f"\n[Error Output]:\n{err_str}"
            
            final_result = result.strip() or "Code executed successfully with no output."
        except Exception:
            final_result = f"Execution failed:\n{traceback.format_exc()}"

        encoded_res = base64.b64encode(final_result.encode('utf-8')).decode('utf-8')
        sys.stdout.write(encoded_res + "\n")
        sys.stdout.flush()

if __name__ == '__main__':
    main()
