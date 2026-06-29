import gradio as gr
import os
from pathlib import Path
import json
import shutil
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

from master_agent import workflow
from state import CodingState

# Initialize workspace cleanup
WORKSPACE_DIR = Path("workspace")

def cleanup_workspace():
    """Clean up the workspace directory between runs."""
    if WORKSPACE_DIR.exists():
        shutil.rmtree(WORKSPACE_DIR)
    WORKSPACE_DIR.mkdir(exist_ok=True)

def format_file_tree(directory: Path, prefix: str = "", is_last: bool = True) -> str:
    """Generate a formatted file tree structure."""
    tree_str = ""
    try:
        items = sorted(directory.iterdir())
    except PermissionError:
        return f"{prefix}[Permission Denied]\n"
    
    for i, item in enumerate(items):
        is_last_item = (i == len(items) - 1)
        current_prefix = "└── " if is_last_item else "├── "
        tree_str += prefix + current_prefix + item.name
        
        if item.is_dir():
            tree_str += "/\n"
            next_prefix = prefix + ("    " if is_last_item else "│   ")
            tree_str += format_file_tree(item, next_prefix, is_last_item)
        else:
            tree_str += f" ({item.stat().st_size} bytes)\n"
    
    return tree_str

def read_file_content(file_path: Path) -> str:
    """Safely read file content."""
    try:
        if file_path.suffix in [".py", ".html", ".css", ".js", ".json", ".md", ".txt"]:
            with open(file_path, "r", encoding="utf-8") as f:
                return f.read()
        else:
            return "[Binary file - cannot display]"
    except Exception as e:
        return f"[Error reading file: {e}]"

def get_project_files() -> dict:
    """Get all generated files from the workspace."""
    files_dict = {}
    
    if not WORKSPACE_DIR.exists():
        return files_dict
    
    for file_path in WORKSPACE_DIR.rglob("*"):
        if file_path.is_file():
            rel_path = file_path.relative_to(WORKSPACE_DIR)
            files_dict[str(rel_path)] = read_file_content(file_path)
    
    return files_dict

def process_request(
    query: str,
    mode: str,
    max_attempts: int
) -> tuple[str, str, str]:
    """
    Process the user's coding request through the JARVIS agent.
    
    Args:
        query: The user's natural language request
        mode: "auto", "script", or "project"
        max_attempts: Maximum number of retry attempts
    
    Returns:
        Tuple of (output_text, file_tree, result_status)
    """
    
    if not query.strip():
        return "❌ Error: Please enter a query", "", "⚠️ No input provided"
    
    try:
        # Clean up workspace
        cleanup_workspace()
        
        # Prepare initial state
        initial_state = {
            "query": query,
            "mode": mode.lower(),
            "attempt": 0,
            "max_attempts": max_attempts,
            "scope": "AUTO"  # Let the agent detect
        }
        
        # Run the workflow
        result = workflow.invoke(initial_state)
        
        # Extract results
        output_text = result.get("output", "No output generated")
        execution_output = result.get("execution_output", "")
        errors = result.get("errors", "")
        
        # Combine outputs
        full_output = ""
        if execution_output:
            full_output += f"📤 **Execution Output:**\n```\n{execution_output}\n```\n\n"
        if errors:
            full_output += f"⚠️ **Errors:**\n```\n{errors}\n```\n\n"
        
        full_output += f"📝 **Agent Output:**\n```\n{output_text}\n```"
        
        # Generate file tree if project
        file_tree = ""
        if WORKSPACE_DIR.exists() and any(WORKSPACE_DIR.iterdir()):
            file_tree = f"📂 **Generated Files:**\n```\n{WORKSPACE_DIR.name}/\n"
            file_tree += format_file_tree(WORKSPACE_DIR)
            file_tree += "```"
        
        status = "✅ Successfully processed request!"
        
        return full_output, file_tree, status
    
    except Exception as e:
        error_msg = f"❌ Error: {str(e)}"
        return error_msg, "", "❌ Request failed"

def get_file_content(file_name: str) -> str:
    """Get content of a specific file from workspace."""
    try:
        file_path = WORKSPACE_DIR / file_name
        if file_path.exists() and file_path.is_file():
            return read_file_content(file_path)
        else:
            return f"❌ File not found: {file_name}"
    except Exception as e:
        return f"❌ Error reading file: {e}"

# Create Gradio interface
with gr.Blocks(
    theme=gr.themes.Soft(primary_hue="blue", secondary_hue="sky"),
    title="JARVIS Coding Agent"
) as demo:
    
    gr.Markdown("""
    # 🤖 JARVIS Coding Agent
    
    An intelligent coding assistant that generates and executes Python code based on natural language prompts.
    
    **Features:**
    - 📝 Script mode: Generate standalone Python scripts
    - 📦 Project mode: Create multi-file projects
    - 🧠 Automatic intent classification
    - 🔧 Error detection and correction
    """)
    
    with gr.Row():
        with gr.Column(scale=2):
            query_input = gr.Textbox(
                label="📝 Your Coding Request",
                placeholder="e.g., Write a Python program that finds the second largest number in a list...",
                lines=4,
                interactive=True
            )
        
        with gr.Column(scale=1):
            mode_select = gr.Radio(
                choices=["auto", "script", "project"],
                value="auto",
                label="🎯 Mode",
                info="Auto-detect or choose specific mode"
            )
            
            max_attempts_slider = gr.Slider(
                minimum=1,
                maximum=5,
                value=3,
                step=1,
                label="🔄 Max Attempts",
                info="Number of error correction attempts"
            )
            
            submit_btn = gr.Button(
                "🚀 Generate Code",
                variant="primary",
                size="lg"
            )
    
    with gr.Tabs():
        with gr.TabItem("📊 Results"):
            with gr.Row():
                status_output = gr.Markdown(
                    value="⏳ Waiting for input...",
                    label="Status"
                )
            
            output_text = gr.Textbox(
                label="📤 Output",
                lines=10,
                interactive=False,
                show_copy_button=True
            )
            
            file_tree_output = gr.Textbox(
                label="📂 Generated Files",
                lines=8,
                interactive=False,
                show_copy_button=True
            )
        
        with gr.TabItem("📂 File Viewer"):
            with gr.Row():
                file_selector = gr.Dropdown(
                    choices=[],
                    label="Select File to View",
                    interactive=True
                )
            
            file_content_display = gr.Code(
                language="python",
                label="File Content",
                interactive=False
            )
            
            def update_file_list(query_text):
                """Update file list whenever workspace changes."""
                if WORKSPACE_DIR.exists():
                    files = list(WORKSPACE_DIR.rglob("*"))
                    file_names = [
                        str(f.relative_to(WORKSPACE_DIR))
                        for f in files if f.is_file()
                    ]
                    return gr.update(choices=file_names if file_names else [])
                return gr.update(choices=[])
            
            def display_file(file_name):
                """Display selected file content."""
                if file_name:
                    return get_file_content(file_name)
                return "Select a file to view its content"
            
            file_selector.change(display_file, inputs=file_selector, outputs=file_content_display)
        
        with gr.TabItem("ℹ️ About"):
            gr.Markdown("""
            ## About JARVIS Coding Agent
            
            JARVIS is an intelligent coding assistant built with:
            - **LangGraph**: For state-graph based workflow orchestration
            - **LangChain**: For LLM integration
            - **Hugging Face**: For large language models
            
            ### How it works:
            1. **Intent Detection**: Classifies your request into CODE, OUTPUT, or BOTH
            2. **Scope Classification**: Determines if you want a script or project
            3. **Planning**: LLM creates a detailed step-by-step plan
            4. **Code Generation**: Generates Python code based on the plan
            5. **Execution**: Runs the code and captures output
            6. **Verification**: Validates results against requirements
            7. **Error Correction**: Automatically fixes errors if needed
            
            ### Modes:
            - **Auto**: Agent detects the best mode automatically
            - **Script**: Generate single Python files
            - **Project**: Generate multi-file projects with directory structure
            
            ### Requirements:
            - Hugging Face API token (set as `HUGGINGFACEHUB_API_TOKEN` env variable)
            - Internet connection for API calls
            """)
    
    # Connect submit button
    def on_submit(query, mode, attempts):
        output, file_tree, status = process_request(query, mode, attempts)
        file_list = update_file_list(query)
        return output, file_tree, status, file_list
    
    submit_btn.click(
        on_submit,
        inputs=[query_input, mode_select, max_attempts_slider],
        outputs=[output_text, file_tree_output, status_output, file_selector]
    )
    
    # Example requests
    gr.Examples(
        examples=[
            ["Write a Python script that calculates the factorial of a number and handles edge cases.", "script", 3],
            ["Create a simple web scraper that fetches data from a public API and saves it to a CSV file.", "script", 3],
            ["Generate a responsive HTML/CSS portfolio website with multiple project cards.", "project", 3],
        ],
        inputs=[query_input, mode_select, max_attempts_slider],
        outputs=[output_text, file_tree_output, status_output],
        fn=on_submit,
        cache_examples=True,
    )

if __name__ == "__main__":
    # Initialize workspace
    cleanup_workspace()
    
    # Launch the app
    demo.launch(
        server_name="0.0.0.0",
        server_port=7860,
        share=False,
        show_error=True,
        debug=False
    )
