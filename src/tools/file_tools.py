import os
from langchain_core.tools import tool
from typing import List, Dict

@tool
def list_directory(path: str) -> List[str]:
    """
    List contents of a directory. 
    Useful for exploring project structure.
    Returns a list of file names.
    """
    try:
        if not os.path.exists(path):
            return [f"Error: Path {path} does not exist"]
        return os.listdir(path)
    except Exception as e:
        return [f"Error: {str(e)}"]

@tool
def read_file(path: str) -> str:
    """
    Read the contents of a file.
    """
    try:
        if not os.path.exists(path):
            return f"Error: Path {path} does not exist"
        with open(path, 'r', encoding='utf-8', errors='ignore') as f:
            return f.read()
    except Exception as e:
        return f"Error reading file: {str(e)}"

@tool
def write_file(path: str, content: str) -> str:
    """
    Write content to a file. 
    Useful for generating test files or reports.
    Will create directories if they don't exist.
    """
    try:
        directory = os.path.dirname(path)
        if directory and not os.path.exists(directory):
            os.makedirs(directory)
        
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)
        return f"Successfully wrote to {path}"
    except Exception as e:
        return f"Error writing file: {str(e)}"
