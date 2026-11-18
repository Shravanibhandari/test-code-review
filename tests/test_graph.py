from langgraph.checkpoint.memory import MemorySaver

from app.graph import build_graph
from app.tools import run_linter_tool


def _start(graph, cfg):
    graph.invoke({"pr_url": "https://github.com/o/r/pull/1"}, cfg)


def test_pauses_before_apply(env):
    g, cfg = build_graph(MemorySaver()), {"configurable": {"thread_id": "t1"}}
    _start(g, cfg)
    assert g.get_state(cfg).next == ("apply_changes_node",)
    assert env["commits"] == []


def test_rejection_rolls_back_to_refactor(env):
    g, cfg = build_graph(MemorySaver()), {"configurable": {"thread_id": "t2"}}
    _start(g, cfg)
    g.update_state(cfg, {"is_approved": False, "reviewer_feedback": "Use list comprehensions"},
                   as_node="apply_changes_node")
    g.invoke(None, cfg)
    assert len(env["prompts"]) == 2
    assert "Use list comprehensions" in env["prompts"][-1]
    assert g.get_state(cfg).next == ("apply_changes_node",)
    assert env["commits"] == []


def test_approval_commits_and_completes(env):
    g, cfg = build_graph(MemorySaver()), {"configurable": {"thread_id": "t3"}}
    _start(g, cfg)
    g.update_state(cfg, {"is_approved": True})
    g.invoke(None, cfg)
    assert env["commits"] == ["a.py"]
    assert g.get_state(cfg).next == ()


def test_linter_detects_syntax_error():
    assert "E999" in run_linter_tool.invoke("def broken(:\n    pass\n")


def test_linter_clean_code():
    assert run_linter_tool.invoke("x = 1\n") == "OK"


def test_linter_black_check_flags_formatting():
    out = run_linter_tool.invoke("x   =   1\n")
    assert "black:" in out
