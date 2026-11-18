import operator
from typing import Annotated, TypedDict


class ReviewState(TypedDict, total=False):
    pr_url: str
    code_contents: dict[str, str]     # filename -> original code
    lint_errors: str
    refactored_code: dict[str, str]   # filename -> proposed code
    is_approved: bool
    reviewer_feedback: str
    history: Annotated[list[str], operator.add]  # reducer appends instead of overwriting
