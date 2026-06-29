# JARVIS Coding Agent

This repository contains a Python-based **intelligent coding assistant** built on top of large language models (LLMs), the `langgraph` state-graph library, and `langchain_huggingface` connectors.  It can automatically generate and execute Python code or entire multi-file projects in response to natural language prompts.

> **Note:** A sample portfolio website project is already included under `workspace/` as an example output from the project agent.

---

## 🚀 Features

- **Script mode** – handle standalone coding requests, run generated Python code, and iteratively fix errors.
- **Project mode** – design filesystem structure, generate multiple files, and scaffold simple applications (e.g. a responsive portfolio website).
- **Intent and scope classification** – determine whether the user wants code or output and if it's a script or project.
- **LLM-driven planning, coding, verification, and error correction** through modular graph nodes.
- **Flexible pipeline** implemented with `langgraph.StateGraph` for easy extension.

---

## 🗂 Repository Structure

```
coding_agent/                # project root
├── llm_model.py             # LLM configuration (HuggingFace endpoint)
├── master_agent.py          # top-level workflow selector
├── project_agent.py         # multi-file/project workflow
├── script_agent.py          # single‑file/script workflow
├── state.py                 # shared graph nodes & helpers
├── tools.py                 # filesystem / execution utilities
├── workspace/               # generated files / demo website
│   ├── ...                  # portfolio website example
│   └── README.md            # documentation for the sample site
└── README.md                # ← you are here
```

---

## 🧠 Prerequisites

1. **Python 3.10+** (or your preferred supported version).
2. Create a virtual environment and install dependencies:
   ```sh
   python -m venv .venv
   .venv\Scripts\activate   # Windows
   pip install -r requirements.txt
   ```
3. **Hugging Face API token** – set `HUGGINGFACEHUB_API_TOKEN` in a `.env` file at the project root.

> Current requirements include `langchain_huggingface`, `langgraph`, `python-dotenv`, and their transitive dependencies.

---

## ⚙️ Configuration

- `llm_model.py` configures the LLM endpoint; you can swap out the `repo_id` or tweak `temperature`, `max_new_tokens`, etc.
- The `.env` file must contain:
  ```ini
  HUGGINGFACEHUB_API_TOKEN=<your_token_here>
  ```

---

## 🧩 Usage

### 1. Script agent (single file)

```python
python script_agent.py
```

The default `initial_state` in `script_agent.py` demonstrates finding the second largest number in a list. To try your own prompt, modify the `query` string.

### 2. Project agent (multi-file)

```python
python project_agent.py
```

Change the `query` in the `initial_state` to generate different projects. The agent will create a `workspace/` subdirectory matching the filesystem plan.

### 3. Master agent (auto selection)

```python
python master_agent.py
```

The master agent reads the prompt and decides whether to use the script or project workflow automatically.

---

## 🛠 How It Works (high level)

1. **Intent & Scope:** classifies the input request into `CODE`/`OUTPUT`/`BOTH` and `SCRIPT`/`PROJECT`.
2. **Planner:** LLM builds a step-by-step plan.
3. **Coding:** LLM writes Python code based on the plan.
4. **Execution:** the code runs in `workspace/` and output/errors are captured.
5. **Verification & Fixing:** LLM checks output against the task and may attempt repairs up to `max_attempts`.
6. **Project Mode:** additional nodes create directories, queue files, generate each file’s contents, and write them.

All nodes are composed using `langgraph.StateGraph` to allow conditional branching and re‑invocation.

---

## 📁 Workspace Example

Under `workspace/` you’ll find a fully generated **portfolio website** (HTML/CSS/JS) created by the project agent. Open `workspace/index.html` in a browser or read the included `workspace/README.md` for details.

---

## 📝 Customization

- Add new nodes in `state.py` for additional behaviors (e.g. testing frameworks, data downloads).
- Modify the graphs in `script_agent.py` or `project_agent.py` to adjust flow or retries.
- Swap the LLM by editing `llm_model.py` or passing different prompts.

---

## 📦 Extending the Agent

1. Create a new Python module with helper functions or tools.
2. Register new nodes with `graph.add_node(...)`.
3. Add transitions or routers via `add_edge`/`add_conditional_edges`.
4. Recompile the workflow and test with an example `initial_state`.

The graph-based design makes experimentation straightforward.

---

## 🧪 Testing

Basic validation occurs when running the scripts; errors and outputs are printed to the console. You can also write your own unit tests by invoking the compiled workflows with custom state dictionaries.

---

## ⚖️ License

This project is provided under the MIT License. Feel free to modify, reuse, or redistribute with attribution.

---

## 🧡 Acknowledgements

Built with ✨ **LangGraph** (state graph) and **LangChain** Hugging Face integration, powered by a chat‑capable LLM.

Happy coding! 🧑‍💻
