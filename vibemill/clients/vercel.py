"""Vercel client.

Workflow we use:
1. create_project(name, github_repo): POST /v9/projects, linked to the
   GitHub repo. Vercel starts a deployment automatically when the linked
   GitHub repo receives its first push.
2. wait_for_ready_deployment(project_name): poll /v6/deployments until the
   newest deployment for this project reaches READY (or ERROR / timeout).
3. delete_project(project_name): DELETE /v9/projects/{idOrName}, called
   from retire.py.

All endpoints honor `teamId` if `VERCEL_TEAM_ID` is set, per SECURITY.md
("scope the token to a dedicated team if pricing permits").
"""

from __future__ import annotations

import logging
import time
from typing import Any

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from ..config import get_settings

log = logging.getLogger(__name__)

API = "https://api.vercel.com"
_TIMEOUT_S = 30
_PAUSE_BETWEEN_CALLS_S = 2  # OPERATIONS.md courtesy
_DEPLOY_POLL_INTERVAL_S = 5
_DEPLOY_POLL_TIMEOUT_S = 300


class VercelError(RuntimeError):
    pass


def _headers() -> dict[str, str]:
    s = get_settings()
    return {"Authorization": f"Bearer {s.VERCEL_TOKEN.get_secret_value()}"}


def _team_param() -> dict[str, str]:
    s = get_settings()
    return {"teamId": s.VERCEL_TEAM_ID} if s.VERCEL_TEAM_ID else {}


@retry(
    reraise=True,
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=4),
    retry=retry_if_exception_type((httpx.TransportError,)),
)
def _request(
    method: str,
    path: str,
    *,
    json: dict | None = None,
    extra_params: dict[str, str] | None = None,
) -> httpx.Response:
    params = _team_param()
    if extra_params:
        params.update(extra_params)
    return httpx.request(
        method,
        f"{API}{path}",
        headers=_headers(),
        params=params,
        json=json,
        timeout=_TIMEOUT_S,
    )


def create_project(name: str, github_repo_full: str) -> dict[str, Any]:
    """Create a project linked to a GitHub repo (e.g. 'vibemill-apps/foo-bar-1234').

    Returns the project record. The first deploy fires automatically as soon
    as the linked GitHub repo receives a push to the default branch.
    """
    payload: dict[str, Any] = {
        "name": name,
        "framework": "nextjs",
        "gitRepository": {"type": "github", "repo": github_repo_full},
    }
    r = _request("POST", "/v9/projects", json=payload)
    if r.status_code not in (200, 201):
        raise VercelError(f"create_project {name}: HTTP {r.status_code}: {r.text[:400]}")
    return r.json()


def get_project(name: str) -> dict[str, Any] | None:
    r = _request("GET", f"/v9/projects/{name}")
    if r.status_code == 404:
        return None
    if r.status_code != 200:
        raise VercelError(f"get_project {name}: HTTP {r.status_code}: {r.text[:300]}")
    return r.json()


def delete_project(name: str) -> None:
    r = _request("DELETE", f"/v9/projects/{name}")
    if r.status_code not in (200, 204):
        raise VercelError(f"delete_project {name}: HTTP {r.status_code}: {r.text[:300]}")


def list_deployments(project_id: str, *, limit: int = 5) -> list[dict[str, Any]]:
    r = _request(
        "GET",
        "/v6/deployments",
        extra_params={"projectId": project_id, "limit": str(limit)},
    )
    if r.status_code != 200:
        raise VercelError(f"list_deployments: HTTP {r.status_code}: {r.text[:300]}")
    return r.json().get("deployments", [])


def wait_for_ready_deployment(
    project_name: str,
    *,
    poll_interval_s: int = _DEPLOY_POLL_INTERVAL_S,
    timeout_s: int = _DEPLOY_POLL_TIMEOUT_S,
) -> dict[str, Any]:
    """Poll until the project's newest deployment reaches READY.

    Raises VercelError on ERROR/CANCELED, TimeoutError on timeout.
    Returns the final deployment record.
    """
    project = get_project(project_name)
    if project is None:
        raise VercelError(f"project {project_name} not found while polling")
    project_id = project["id"]

    deadline = time.monotonic() + timeout_s
    last_state = "unknown"
    while time.monotonic() < deadline:
        deployments = list_deployments(project_id, limit=1)
        if deployments:
            d = deployments[0]
            state = d.get("readyState") or d.get("state") or "UNKNOWN"
            if state != last_state:
                log.info("vercel deploy %s state=%s", project_name, state)
                last_state = state
            if state == "READY":
                return d
            if state in ("ERROR", "CANCELED"):
                raise VercelError(f"deploy {project_name} ended in state {state}")
        time.sleep(poll_interval_s)
    raise TimeoutError(f"deploy {project_name} did not reach READY within {timeout_s}s")


def deployment_url(deployment: dict[str, Any]) -> str:
    """Best public URL for a deployment record. Prefers the Vercel default."""
    if alias := deployment.get("alias"):
        # alias is a list of strings like ['foo-abc.vercel.app']
        return f"https://{alias[0]}" if alias else ""
    if url := deployment.get("url"):
        return f"https://{url}"
    return ""
