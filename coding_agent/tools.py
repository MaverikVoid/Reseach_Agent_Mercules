import subprocess
import os
import sys
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
WORKSPACE = os.path.join(BASE_DIR, "workspace")

def write_file(file_name:str, code:str) -> str:
    """
    Writes generated code to a file inside workspace.
    """ 
    os.makedirs(WORKSPACE, exist_ok=True)
    filepath = os.path.join(WORKSPACE,file_name)

    with open(filepath,"w",encoding="utf-8") as f:
        f.write(code)

    return f"File written successfully to {filepath}"
def write_file_project(file_path: str, code: str):
    full_path = os.path.join("workspace", file_path)
    os.makedirs(os.path.dirname(full_path), exist_ok=True)

    with open(full_path, "w", encoding="utf-8") as f:
        f.write(code)

    return f"Wrote {file_path}"


def run_python(file_name:str):
    """
    Executes a Python file inside workspace.
    """
    filepath = os.path.join(WORKSPACE,file_name)

    result = subprocess.run(
        [sys.executable,filepath],
        capture_output=True,
        text=True,
        timeout=10
    )

    return {
        "stdout":result.stdout,
        "stderr":result.stderr
    }

def directory_creator(path:str):
    os.makedirs(path,exist_ok=True)
    return f"Directory Created: {path}"

