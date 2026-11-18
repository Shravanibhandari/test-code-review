import uuid

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel

from app.config import CHECKPOINT_DB
from app.graph import build_graph, default_checkpointer

router = APIRouter(prefix="/api")
graph = build_graph(default_checkpointer(CHECKPOINT_DB))


class ApprovalPayload(BaseModel):
    approved: bool
    feedback: str | None = None


def _cfg(thread_id):
    return {"configurable": {"thread_id": thread_id}}


def _run(state_or_none, thread_id):
    graph.invoke(state_or_none, _cfg(thread_id))
    snap = graph.get_state(_cfg(thread_id))
    print(f"[thread {thread_id}] status={'awaiting_approval' if snap.next else 'completed'} next={snap.next}")


@router.post("/webhooks/github")
def github_webhook(payload: dict, bg: BackgroundTasks):
    pr = payload.get("pull_request")
    if pr:
        pr_url = pr["html_url"]
    elif payload.get("repository_url") and payload.get("branch"):  # mock payload (Test Case 1)
        pr_url = f"{payload['repository_url'].rstrip('/')}/tree/{payload['branch']}"
    else:
        raise HTTPException(422, "Need pull_request.html_url or repository_url + branch")
    thread_id = str(uuid.uuid4())
    bg.add_task(_run, {"pr_url": pr_url, "history": ["webhook received"]}, thread_id)
    return {"thread_id": thread_id, "status": "started"}


@router.post("/reviews/{thread_id}/approve")
def approve(thread_id: str, body: ApprovalPayload, bg: BackgroundTasks):
    snap = graph.get_state(_cfg(thread_id))
    if not snap.values:
        raise HTTPException(404, "Unknown thread")
    if snap.next != ("apply_changes_node",):
        raise HTTPException(409, f"Thread is not awaiting approval (next={snap.next})")

    if body.approved:
        graph.update_state(_cfg(thread_id), {"is_approved": True,
                                             "reviewer_feedback": body.feedback or "",
                                             "history": ["approved by reviewer"]})
    else:
        if not body.feedback:
            raise HTTPException(422, "feedback is required when approved=false")
        graph.update_state(_cfg(thread_id),
                           {"is_approved": False, "reviewer_feedback": body.feedback,
                            "history": [f"rejected: {body.feedback}"]},
                           as_node="apply_changes_node")  # triggers the re-route
    bg.add_task(_run, None, thread_id)
    return {"thread_id": thread_id, "status": "resumed"}


@router.get("/reviews/{thread_id}")
def get_review(thread_id: str):
    snap = graph.get_state(_cfg(thread_id))
    return {"next": snap.next, "state": snap.values}
