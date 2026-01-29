import subprocess
from langchain_core.tools import tool

@tool
def run_shell_command(command: str) -> str:
    """
    Execute a shell command.
    Useful for running tests (e.g., 'pytest', 'go test', 'gcc').
    Returns stdout and stderr.
    """
    try:
        result = subprocess.run(
            command, 
            shell=True, 
            capture_output=True, 
            text=True, 
            timeout=5000  # 5000 seconds timeout
        )
        return f"STDOUT:\n{result.stdout}\n\nSTDERR:\n{result.stderr}\n\nReturn Code: {result.returncode}"
    except subprocess.TimeoutExpired:
        return "Error: Command timed out after 5000 seconds."
    except Exception as e:
        return f"Error executing command: {str(e)}"
