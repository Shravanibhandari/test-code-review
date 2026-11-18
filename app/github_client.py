import re

from github import Github

from app.config import GITHUB_TOKEN


def _gh():
    return Github(GITHUB_TOKEN)


def parse_target(url: str):
    """Accepts .../owner/repo/pull/12 or .../owner/repo/tree/branch."""
    m = re.search(r"github\.com/([^/]+/[^/]+)/pull/(\d+)", url)
    if m:
        return m.group(1), int(m.group(2)), None
    m = re.search(r"github\.com/([^/]+/[^/]+)/tree/(.+)", url)
    if m:
        return m.group(1), None, m.group(2)
    raise ValueError(f"Unsupported GitHub URL: {url}")


def _resolve(url: str):
    repo_name, pr_number, branch = parse_target(url)
    repo = _gh().get_repo(repo_name)
    pr = None
    if pr_number:
        pr = repo.get_pull(pr_number)
        branch = pr.head.ref
    return repo, pr, branch


def get_pr_files(url: str) -> dict[str, str]:
    repo, pr, branch = _resolve(url)
    if pr:
        paths = [f.filename for f in pr.get_files()
                 if f.filename.endswith(".py") and f.status != "removed"]
    else:  # webhook mock with just repo + branch
        paths = [c.path for c in repo.get_contents("", ref=branch) if c.path.endswith(".py")]
    return {p: repo.get_contents(p, ref=branch).decoded_content.decode() for p in paths}


def commit_file(url: str, path: str, content: str, message: str) -> str:
    repo, _, branch = _resolve(url)
    current = repo.get_contents(path, ref=branch)
    result = repo.update_file(path, message, content, current.sha, branch=branch)
    return result["commit"].sha
