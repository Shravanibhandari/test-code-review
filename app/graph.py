import sqlite3

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph

from app import nodes
from app.state import ReviewState


def route_after_apply(state):
    # reached after approval (node ran) or after rejection (update_state as_node)
    return END if state.get("is_approved") else "propose_refactor_node"


def build_graph(checkpointer):
    g = StateGraph(ReviewState)
    g.add_node("fetch_pr_node", nodes.fetch_pr_node)
    g.add_node("lint_code_node", nodes.lint_code_node)
    g.add_node("propose_refactor_node", nodes.propose_refactor_node)
    g.add_node("apply_changes_node", nodes.apply_changes_node)

    g.add_edge(START, "fetch_pr_node")
    g.add_edge("fetch_pr_node", "lint_code_node")
    g.add_edge("lint_code_node", "propose_refactor_node")
    g.add_edge("propose_refactor_node", "apply_changes_node")
    g.add_conditional_edges("apply_changes_node", route_after_apply,
                            {END: END, "propose_refactor_node": "propose_refactor_node"})

    return g.compile(checkpointer=checkpointer, interrupt_before=["apply_changes_node"])


def default_checkpointer(path="checkpoints.db"):
    return SqliteSaver(sqlite3.connect(path, check_same_thread=False))
