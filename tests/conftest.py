import pytest

from app import nodes


@pytest.fixture
def env(monkeypatch):
    calls = {"prompts": [], "commits": []}
    monkeypatch.setattr(nodes, "get_pr_files", lambda url: {"a.py": "import os\nx=1\n"})
    monkeypatch.setattr(nodes, "_call_llm",
                        lambda p: calls["prompts"].append(p) or "```python\nx = 1\n```")
    monkeypatch.setattr(nodes, "commit_file",
                        lambda url, n, c, m: calls["commits"].append(n) or "abc1234def")
    return calls
