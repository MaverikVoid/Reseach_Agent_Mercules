from state import CodingState, coding_node, write_file_node, run_python_node, should_continue, fix_error_node, planner_node, verifier_node, intent_node, after_run_router
from langgraph.graph import StateGraph, START, END

graph = StateGraph(CodingState)

graph.add_node('coding_node',coding_node)
graph.add_node("planner_node",planner_node)
graph.add_node('write_file_node',write_file_node)
graph.add_node("run_python_node",run_python_node)
graph.add_node("fix_error_node",fix_error_node)
graph.add_node("verify", verifier_node)
graph.add_node("intent", intent_node)


graph.add_edge(START, "intent")
graph.add_edge("intent", "planner_node")
graph.add_edge("planner_node","coding_node")
graph.add_edge('coding_node',"write_file_node")
graph.add_edge("write_file_node","run_python_node")
graph.add_conditional_edges(
    "run_python_node",
    after_run_router,
    {
        "verify": "verify",
        END: END
    }
)

graph.add_conditional_edges(
    "verify",
    should_continue,
    {
        "fix": "fix_error_node",
        END: END
    }
)


graph.add_edge("fix_error_node","write_file_node")

script_workflow = graph.compile()

if __name__ == "__main__":
    initial_state = {
    "query": """Write a Python program that finds the second largest number in a list and handles duplicate values correctly. Print the result.
""",
    "attempt": 0,
    "max_attempts": 3
}
    final_state = script_workflow.invoke(initial_state)

    if final_state["execution_error"]:
        print("\n❌ Agent failed after maximum retries.")
        print(final_state["execution_error"])
    else:
        print("\n✅ Program output:\n")
        print(final_state["execution_output"])



