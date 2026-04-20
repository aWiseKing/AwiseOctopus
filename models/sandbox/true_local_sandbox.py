import subprocess
import sys
import os
import base64
import time

class TrueLocalSandbox:
    """
    A true local sandbox that utilizes Docker if available, otherwise falls back
    to a local subprocess. It communicates with a runner script (`runner.py`) 
    via base64-encoded strings over stdin/stdout to persist state across executions
    and safely handle multi-line code/output.
    """

    def __init__(self, use_docker=None, **kwargs):
        self.runner_path = os.path.join(os.path.dirname(__file__), 'runner.py')
        self.process = None
        
        if use_docker is None:
            # Auto-detect docker
            try:
                # Use a fast command to check if docker daemon is running
                subprocess.run(['docker', 'info'], capture_output=True, check=True, timeout=5)
                self.use_docker = True
            except Exception:
                self.use_docker = False
        else:
            self.use_docker = use_docker

        self.model = "docker-sandbox" if self.use_docker else "subprocess-sandbox"
        self._start_process()

    def _start_process(self):
        if self.use_docker:
            runner_dir = os.path.dirname(self.runner_path)
            # Use a python slim image
            cmd = [
                'docker', 'run', '-i', '--rm', 
                '-v', f'{runner_dir}:/sandbox', 
                '-w', '/sandbox', 
                'python:3.10-slim', 
                'python', '-u', 'runner.py'
            ]
        else:
            cmd = [sys.executable, '-u', self.runner_path]
        
        try:
            self.process = subprocess.Popen(
                cmd, 
                stdin=subprocess.PIPE, 
                stdout=subprocess.PIPE, 
                stderr=subprocess.STDOUT,
                text=True,
                encoding='utf-8',
                bufsize=1  # Line buffered
            )
            # Give it a short moment to start
            time.sleep(0.5)
            if self.process.poll() is not None:
                out = self.process.stdout.read()
                raise RuntimeError(f"Sandbox process exited prematurely with output: {out}")
        except Exception as e:
            raise RuntimeError(f"Failed to start sandbox process: {e}")

    def execute_code(self, code: str) -> str:
        """
        Executes the provided Python code in the sandbox.
        """
        if not self.process or self.process.poll() is not None:
            return "Sandbox process is not running or has crashed."

        try:
            # Encode code to base64 to avoid newline and buffering issues
            encoded_code = base64.b64encode(code.encode('utf-8')).decode('utf-8')
            
            # Send to process
            self.process.stdin.write(encoded_code + "\n")
            self.process.stdin.flush()
            
            # Read result
            result_line = self.process.stdout.readline()
            
            if not result_line:
                return "Failed to read from sandbox process. Process might have crashed."
            
            # Decode result
            decoded_result = base64.b64decode(result_line.strip()).decode('utf-8')
            return decoded_result
        except Exception as e:
            return f"Sandbox communication error: {e}"

    def close(self):
        """
        Terminates the sandbox process and cleans up resources.
        """
        if self.process and self.process.poll() is None:
            try:
                self.process.stdin.close()
            except Exception:
                pass
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
