
import uuid

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.config import CHECKPOINT_DB
from app.graph import build_graph, default_checkpointer

router = APIRouter(prefix="/api")

graph = build_graph(default_checkpointer(CHECKPOINT_DB))


class ApprovalPayload(BaseModel):
    approved: bool
    feedback: str | None = None


def _cfg(thread_id: str):
    return {"configurable": {"thread_id": thread_id}}


def _run(state_or_none, thread_id: str):
    config = _cfg(thread_id)

    try:
        graph.invoke(state_or_none, config)
        snap = graph.get_state(config)

        status = "awaiting_approval" if snap.next else "completed"

        return {
            "thread_id": thread_id,
            "status": status,
            "next": list(snap.next),
            "state": snap.values,
        }

    except Exception as exc:
        print(f"[ERROR] Thread {thread_id}: {exc}")
        raise


@router.post("/webhooks/github")
def github_webhook(payload: dict):
    pr = payload.get("pull_request")

    if pr:
        pr_url = pr.get("html_url")

    elif payload.get("repository_url") and payload.get("branch"):
        # Mock payload for testing
        pr_url = (
            f"{payload['repository_url'].rstrip('/')}"
            f"/tree/{payload['branch']}"
        )

    else:
        raise HTTPException(
            status_code=422,
            detail="Need pull_request.html_url or repository_url + branch",
        )

    thread_id = str(uuid.uuid4())

    initial_state = {
        "pr_url": pr_url,
        "history": ["webhook received"],
    }

    try:
        return _run(initial_state, thread_id)

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Review execution failed: {str(exc)}",
        )


@router.post("/reviews/{thread_id}/approve")
def approve(thread_id: str, body: ApprovalPayload):
    config = _cfg(thread_id)

    snap = graph.get_state(config)

    if not snap.values:
        raise HTTPException(
            status_code=404,
            detail="Unknown thread ID",
        )

    if snap.next != ("apply_changes_node",):
        raise HTTPException(
            status_code=409,
            detail=f"Thread is not awaiting approval. Next: {snap.next}",
        )

    if not body.approved and not body.feedback:
        raise HTTPException(
            status_code=422,
            detail="Feedback is required when rejecting.",
        )

    try:
        if body.approved:
            graph.update_state(
                config,
                {
                    "is_approved": True,
                    "reviewer_feedback": body.feedback or "",
                    "history": ["approved by reviewer"],
                },
            )

        else:
            graph.update_state(
                config,
                {
                    "is_approved": False,
                    "reviewer_feedback": body.feedback,
                    "history": [f"rejected: {body.feedback}"],
                },
                as_node="apply_changes_node",
            )

        # Resume the graph immediately and return its actual result.
        result = _run(None, thread_id)

        return result

    except HTTPException:
        raise

    except Exception as exc:
        print(f"[APPROVAL ERROR] Thread {thread_id}: {exc}")

        raise HTTPException(
            status_code=500,
            detail=f"Failed to resume review: {str(exc)}",
        )


@router.get("/reviews/{thread_id}")
def get_review(thread_id: str):
    config = _cfg(thread_id)

    snap = graph.get_state(config)

    if not snap.values:
        raise HTTPException(
            status_code=404,
            detail="Unknown thread ID",
        )

    return {
        "thread_id": thread_id,
        "status": "awaiting_approval" if snap.next else "completed",
        "next": list(snap.next),
        "state": snap.values,
    }


@router.get("/reviews")
def list_reviews():
    return {
        "message": "Use GET /reviews/{thread_id} to inspect a review.",
        "endpoints": [
            "POST /webhooks/github",
            "GET /reviews/{thread_id}",
            "POST /reviews/{thread_id}/approve",
        ],
    }



