from langgraph.graph import StateGraph, START, END

from state import (
    CodingState,

    # nodes
    intent_node,
    planner_node,
    filesystem_planner_node,
    directory_creator_node,

    init_file_queue_node,
    file_generator_node,
    write_project_file_node,
    next_file_node,

    verifier_node,
    fix_error_node,

    # routers
    file_router,
    should_continue,
    after_run_router,
)

# --------------------------------------------------
# Create graph
# --------------------------------------------------

graph = StateGraph(CodingState)

# --------------------------------------------------
# Register nodes
# --------------------------------------------------

graph.add_node("intent", intent_node)
graph.add_node("planner", planner_node)

graph.add_node("filesystem_planner", filesystem_planner_node)
graph.add_node("create_directories", directory_creator_node)

graph.add_node("init_file_queue", init_file_queue_node)
graph.add_node("file_generator", file_generator_node)
graph.add_node("write_project_file", write_project_file_node)
graph.add_node("next_file", next_file_node)

graph.add_node("verify", verifier_node)
graph.add_node("fix_error", fix_error_node)

# --------------------------------------------------
# Main execution flow
# --------------------------------------------------

graph.add_edge(START, "intent")
graph.add_edge("intent", "planner")

graph.add_edge("planner", "filesystem_planner")
graph.add_edge("filesystem_planner", "create_directories")

# --------------------------------------------------
# File generation loop
# --------------------------------------------------

graph.add_edge("create_directories", "init_file_queue")
graph.add_edge("init_file_queue", "file_generator")
graph.add_edge("file_generator", "write_project_file")
graph.add_edge("write_project_file", "next_file")

# Loop controller
graph.add_conditional_edges(
    "next_file",
    file_router,
    {
        "next_file": "file_generator",
        END: END
    }
)

# --------------------------------------------------
# Compile workflow
# --------------------------------------------------

project_workflow = graph.compile()

# --------------------------------------------------
# Run
# --------------------------------------------------

if __name__ == "__main__":

    initial_state = {
        "query": "Create a responsive portfolio website using HTML, CSS and JavaScript.",
        "attempt": 0,
        "max_attempts": 3
    }

    final_state = project_workflow.invoke(initial_state)

    print("\n✅ PROJECT GENERATION COMPLETE")
