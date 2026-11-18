import re

from langchain_openai import ChatOpenAI

from app.github_client import commit_file, get_pr_files
from app.tools import run_linter_tool


def _call_llm(prompt: str) -> str:  # isolated so tests can patch it
    return ChatOpenAI(model="gpt-4o-mini", temperature=0).invoke(prompt).content


def _strip_fences(text: str) -> str:
    m = re.search(r"```(?:python)?\n(.*?)```", text, re.S)
    return (m.group(1) if m else text).strip() + "\n"


def fetch_pr_node(state):
    files = get_pr_files(state["pr_url"])
    return {"code_contents": files, "history": [f"fetched {len(files)} file(s)"]}


def lint_code_node(state):
    source = state.get("refactored_code") or state["code_contents"]
    report = [f"## {name}\n{run_linter_tool.invoke(code)}" for name, code in source.items()]
    return {"lint_errors": "\n".join(report), "history": ["linted code"]}


def propose_refactor_node(state):
    feedback = state.get("reviewer_feedback", "")
    out = {}
    for name, code in state["code_contents"].items():
        prompt = (
            "Refactor this Python file to fix the lint errors. "
            "Preserve the original functional logic. Return ONLY the full file in a ```python block.\n\n"
            f"Lint report:\n{state.get('lint_errors', '')}\n\n"
            + (f"Reviewer feedback (must follow):\n{feedback}\n\n" if feedback else "")
            + f"File {name}:\n```python\n{code}\n```"
        )
        out[name] = _strip_fences(_call_llm(prompt))
    return {"refactored_code": out, "is_approved": False,
            "history": [f"proposed refactor (feedback: {feedback or 'none'})"]}


def apply_changes_node(state):
    shas = [commit_file(state["pr_url"], n, c, f"refactor: automated fixes for {n}")
            for n, c in state["refactored_code"].items()]
    return {"history": [f"committed {len(shas)} file(s): {', '.join(s[:7] for s in shas)}"]}
