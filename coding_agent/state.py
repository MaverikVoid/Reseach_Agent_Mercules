from tools import write_file, run_python, directory_creator, write_file_project
from langgraph.graph import END
from typing import TypedDict
from llm_model import model
import json
import os
import re

class CodingState(TypedDict):
    query: str

    # classification
    task_type: str        # CODE / OUTPUT / BOTH
    scope: str            # SCRIPT / PROJECT

    # planning
    plan: str
    filesystem_plan: dict

    # multi-file support
    file_queue: list
    current_file: str

    # code
    code: str

    # execution
    execution_output: str
    execution_error: str
    verification_result: str

    attempt: int
    max_attempts: int


def extract_json(text: str) -> dict:
    """
    Extract first JSON object from LLM output.
    """
    match = re.search(r"\{[\s\S]*\}", text)
    if not match:
        raise ValueError("No JSON found in LLM output")

    return json.loads(match.group())


def log(message: str):
    print(message, flush=True)

def clean_code(text: str) -> str:
    return (
        text.replace("```python", "")
            .replace("```", "")
            .strip()
    )

def scope_classifier_node(state: CodingState):
    log("\n[Scope] Determining task scope...")

    prompt = f"""
Classify the user's request.

USER REQUEST:
{state['query']}

Respond with ONLY one word:

SCRIPT  → small standalone program
PROJECT → multi-file system, framework, automation, or application
"""

    scope = model.invoke(prompt).content.strip().upper()

    if scope not in {"SCRIPT", "PROJECT"}:
        scope = "SCRIPT"

    log(f"[Scope] Task scope → {scope}")

    return {"scope": scope}


def coding_node(state: CodingState):
    log("\n[Coder] Generating Python code...")

    query = state["query"]
    plan = state["plan"]

    prompt = f"""
You are a senior Python developer.

USER TASK:
{query}

EXECUTION PLAN:
{plan}

INSTRUCTIONS:
- Follow the plan strictly
- Do NOT add input()
- Code must run automatically
- Output only Python code
"""

    code = clean_code(model.invoke(prompt).content.strip())
    log("[Coder] Code generated")
    return {"code": code}


def filesystem_planner_node(state: CodingState):
    log("\n[FS-PLANNER] Designing project structure...")

    prompt = f"""
You are a senior software architect.

Design the filesystem structure needed to
complete the following task.

TASK:
{state['query']}

Return ONLY valid JSON.

RULES:
- No markdown
- No explanation
- Output must start with {{ and end with }}

JSON SCHEMA:
{{
  "project_root": "string",
  "directories": ["dir1", "dir2"],
  "files": {{
      "path/filename.ext": "short description"
  }}
}}
"""

    raw = model.invoke(prompt).content.strip()

    try:
        plan = extract_json(raw)
    except Exception as e:
        print("\n[RAW LLM OUTPUT]")
        print(raw)
        raise ValueError("Filesystem planner returned invalid JSON")

    log("[FS-PLANNER] Filesystem plan created")

    return {"filesystem_plan": plan}


def write_file_node(state:CodingState):
    log("\n[Tool] Writing file → workspace/main.py")
    result = write_file(
        file_name="main.py",
        code = state['code']
    )
    return{"file_status":result}

def write_project_file_node(state: CodingState):
    file_path = state["current_file"]

    log(f"[FS] Writing → {file_path}")

    write_file_project(
        file_path=file_path,
        code=state["code"]
    )

    return {}


def run_python_node(state:CodingState):
    attempt = state["attempt"] + 1
    max_attempts = state["max_attempts"]

    log(f"\n[Executor] Running Python (attempt {attempt}/{max_attempts})")

    result = run_python("main.py")

    if result["stderr"]:
        log("[Executor] Error detected")
    else:
        log("[Executor] Execution successful")

    return {
        "execution_output": result["stdout"],
        "execution_error": result["stderr"],
        "attempt": attempt
    }

def fix_error_node(state:CodingState):
    log("\n[Fixer] Fixing code based on error...")
    prompt = f"""
The following Python code has errors.

CODE:
{state['code']}

ERROR:
{state['execution_error']}

TASK:
Fix the code.

RULES:
- Return ONLY corrected Python code
- No explanation
"""
    response = clean_code(model.invoke(prompt).content.strip())
    log("[Fixer] Code fixed")
    return{"code":response}

def after_run_router(state: CodingState):
    if state["task_type"] == "CODE":
        return END
    return "verify"

def file_router(state: CodingState):
    if state["file_queue"]:
        return "next_file"
    return END


def should_continue(state: CodingState):

    # 1. Python error → must fix
    if state["execution_error"]:
        if state["attempt"] < state["max_attempts"]:
            return "fix"
        return END

    # 2. Output incorrect → must fix
    if not state["verification_result"].startswith("SUCCESS"):
        if state["attempt"] < state["max_attempts"]:
            return "fix"
        return END

    # 3. Everything correct
    return END

def intent_node(state: CodingState):
    log("\n[Intent] Determining task intent...")
    prompt = f"""
Classify the user's request.

USER REQUEST:
{state['query']}

Respond with ONLY ONE word:
CODE
OUTPUT
BOTH
"""

    intent = model.invoke(prompt).content.strip()

    if intent not in {"CODE", "OUTPUT", "BOTH"}:
        intent = "CODE"
    
    log(f"[Intent] Task type → {intent}")

    return {"task_type": intent}

def planner_node(state: CodingState):
    log("\n[Planner] Creating execution plan...")

    query = state["query"]

    prompt = f"""
You are a senior software architect.

Your job is to create a clear step-by-step plan
to solve the user's request.

TASK:
{query}

RULES:
- Do NOT write code
- Do NOT explain concepts
- Return a numbered execution plan
- Keep it short (5–8 steps max)
"""

    plan = model.invoke(prompt).content.strip()
    log("[Planner] Plan created")
    return {"plan": plan}

def verifier_node(state: CodingState):
    log("\n[Verifier] Checking if output satisfies task...")

    prompt = f"""
You are a strict software tester.

USER TASK:
{state['query']}

PROGRAM OUTPUT:
{state['execution_output']}

Your job is to determine whether the output
correctly satisfies the user request.

Rules:
- Respond with ONLY one of the following:
  SUCCESS
  FAILURE: <short reason>

Do not explain anything else.
"""

    result = model.invoke(prompt).content.strip()

    log(f"[Verifier] Result → {result}")

    return {"verification_result": result}

def directory_creator_node(state:CodingState):
    log("\n[FS] Creating directories...")

    root = state["filesystem_plan"]['project_root']
    dirs = state["filesystem_plan"].get("directories", [])

    directory_creator(root)

    for d in dirs:
        directory_creator(os.path.join(root,d))

    return {}

def file_generator_node(state: CodingState):
    file_path = state["current_file"]

    log(f"\n[FILE-GEN] Generating {file_path}")

    prompt = f"""
You are generating the file:

{file_path}

PROJECT PURPOSE:
{state['query']}

FILESYSTEM STRUCTURE:
{state['filesystem_plan']}

Write ONLY the content of this file.
"""

    code = clean_code(model.invoke(prompt).content)

    return {"code": code}

def init_file_queue_node(state: CodingState):
    log("\n[FS] Initializing file queue...")

    files = list(state["filesystem_plan"]["files"].keys())

    return {
        "file_queue": files,
        "current_file": files[0]
    }
def next_file_node(state: CodingState):
    queue = state["file_queue"]

    if not queue:
        return {}

    queue.pop(0)

    if queue:
        return {
            "file_queue": queue,
            "current_file": queue[0]
        }

    return {
        "file_queue": [],
        "current_file": None
    }

def master_router(state: CodingState):
    if state["scope"] == "PROJECT":
        return "project_graph"
    return "script_graph"
