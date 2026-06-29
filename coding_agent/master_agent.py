from langgraph.graph import StateGraph, START, END

from state import (
    CodingState,
    intent_node,
    scope_classifier_node
)

from script_agent import script_workflow
from project_agent import project_workflow


graph = StateGraph(CodingState)

graph.add_node("intent", intent_node)
graph.add_node("scope", scope_classifier_node)

graph.add_node("script_graph", script_workflow)
graph.add_node("project_graph", project_workflow)

graph.add_edge(START, "intent")
graph.add_edge("intent", "scope")

graph.add_conditional_edges(
    "scope",
    lambda s: "project_graph" if s["scope"] == "PROJECT" else "script_graph",
    {
        "project_graph": "project_graph",
        "script_graph": "script_graph"
    }
)

graph.add_edge("script_graph", END)
graph.add_edge("project_graph", END)

workflow = graph.compile()

initial_state = {
    "query": """Write a Python program that finds the second largest number in a list and handles duplicate values correctly. Print the result.
""",
    "attempt": 0,
    "max_attempts": 3
}
workflow.invoke(initial_state)
