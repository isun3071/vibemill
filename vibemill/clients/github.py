"""GitHub client.

Three operations the mill needs:
- create_repo(name): POST /orgs/{org}/repos
- push_directory(name, src, message): git init + add + commit + push to the
  newly-created repo via the token-embedded HTTPS URL
- archive_repo(name): PATCH /repos/{org}/{name} { archived: true }

Commits are authored as "Vibe Mill <mill@vibemill.dev>" so the history
honestly identifies the source. The token is embedded in the remote URL
only for the push and is not written to .git/config (we use a one-shot
push URL).
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import httpx
from git import Actor, Repo
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from ..config import get_settings

log = logging.getLogger(__name__)

API = "https://api.github.com"
_TIMEOUT_S = 30
MILL_AUTHOR = Actor("Vibe Mill", "mill@vibemill.dev")


class GitHubError(RuntimeError):
    pass


def _headers() -> dict[str, str]:
    s = get_settings()
    return {
        "Authorization": f"Bearer {s.GITHUB_TOKEN.get_secret_value()}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def _retryable(exc: BaseException) -> bool:
    return isinstance(exc, (GitHubError, httpx.TransportError)) and (
        not isinstance(exc, GitHubError) or "5" in str(exc)[:6] or "429" in str(exc)[:6]
    )


@retry(
    reraise=True,
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=4),
    retry=retry_if_exception_type((httpx.TransportError,)),
)
def _request(method: str, path: str, json: dict | None = None) -> httpx.Response:
    r = httpx.request(method, f"{API}{path}", headers=_headers(), json=json, timeout=_TIMEOUT_S)
    return r


def create_repo(
    name: str,
    description: str,
    *,
    private: bool = False,
    homepage: str | None = None,
) -> dict[str, Any]:
    """Create a new repo under the configured org. Returns the API response."""
    s = get_settings()
    payload: dict[str, Any] = {
        "name": name,
        "description": description,
        "private": private,
        "auto_init": False,
        "has_issues": False,
        "has_projects": False,
        "has_wiki": False,
    }
    if homepage:
        payload["homepage"] = homepage
    r = _request("POST", f"/orgs/{s.GITHUB_ORG}/repos", json=payload)
    if r.status_code not in (201, 200):
        raise GitHubError(f"create_repo {name}: HTTP {r.status_code}: {r.text[:300]}")
    return r.json()


def archive_repo(name: str) -> None:
    s = get_settings()
    r = _request("PATCH", f"/repos/{s.GITHUB_ORG}/{name}", json={"archived": True})
    if r.status_code != 200:
        raise GitHubError(f"archive_repo {name}: HTTP {r.status_code}: {r.text[:300]}")


def repo_https_url(name: str) -> str:
    s = get_settings()
    return f"https://github.com/{s.GITHUB_ORG}/{name}"


def push_url_with_token(name: str) -> str:
    """A one-shot HTTPS URL with the token embedded for `git push`.

    Use only as the URL argument to `git push`; never write it to .git/config.
    """
    s = get_settings()
    token = s.GITHUB_TOKEN.get_secret_value()
    return f"https://x-access-token:{token}@github.com/{s.GITHUB_ORG}/{name}.git"


def push_directory(
    *,
    name: str,
    src: Path,
    commit_message: str,
    branch: str = "main",
) -> str:
    """Initialize a git repo at `src`, commit everything, push to the GitHub repo
    of the same name. Returns the commit SHA.

    The remote URL with embedded token is used only for the push and not
    persisted to .git/config.
    """
    if not src.is_dir():
        raise FileNotFoundError(src)

    repo = Repo.init(src, initial_branch=branch)
    repo.git.add(A=True)
    commit = repo.index.commit(commit_message, author=MILL_AUTHOR, committer=MILL_AUTHOR)

    push_url = push_url_with_token(name)
    # Use a one-shot push without persisting the token-bearing URL.
    repo.git.push(push_url, f"HEAD:{branch}")
    return commit.hexsha
