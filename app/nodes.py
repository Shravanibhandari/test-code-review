import os
import re

from langchain_groq import ChatGroq

from app.github_client import commit_file, get_pr_files
from app.tools import run_linter_tool


def _call_llm(prompt: str) -> str:  # isolated so tests can patch it
    llm = ChatGroq(
        model="llama-3.3-70b-versatile",
        temperature=0,
        api_key=os.getenv("GROQ_API_KEY"),
    )
    return llm.invoke(prompt).content


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
    if not state.get("is_approved"):
        return {
            "history": ["commit blocked: reviewer approval required"]
        }

    shas = [
        commit_file(
            state["pr_url"],
            name,
            code,
            f"refactor: automated fixes for {name}"
        )
        for name, code in state["refactored_code"].items()
    ]

    return {
        "history": [
            f"committed {len(shas)} file(s): "
            f"{', '.join(sha[:7] for sha in shas)}"
        ]
    }
