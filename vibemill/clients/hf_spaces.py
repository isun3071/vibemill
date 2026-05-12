"""Hugging Face Spaces client.

Workflow Vibe Mill uses for Python archetypes:
1. create_space(name, sdk='gradio'): POST /api/repos/create. Returns the
   Space record (we keep only the URL).
2. push_url_with_token(name): build the git remote URL with the token
   embedded. github_publish-style: never persist to .git/config.
3. wait_for_running(name, timeout_s): poll /api/spaces/{user}/{name} until
   runtime.stage == 'RUNNING' (or BUILD_ERROR / RUNTIME_ERROR / timeout).
4. delete_space(name): DELETE /api/repos/delete.

HF builds the Space automatically on first `git push`. Cold builds we
measured during Bundle H test: 30-90s BUILDING + ~25s APP_STARTING = ~60s
total. Timeout is set to 10min to handle slower cold containers.

Per Bundle H test findings (vibemill-test-gradio):
- Pin python_version: "3.11" in the Space README frontmatter. HF defaults
  to 3.13 which dropped audioop from stdlib; many Python AI libs break.
- Pin gradio>=5.15,<6 in requirements.txt. Older 5.x had HfFolder import
  issues; 4.x had audioop issues.
- Public URL format: https://{user}-{repo-name}.hf.space (lowercase, dashes).

No org used in V0; HF_USERNAME is the personal account.
"""

from __future__ import annotations

import logging
import time
from typing import Any

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from ..config import get_settings

log = logging.getLogger(__name__)

API = "https://huggingface.co"
_TIMEOUT_S = 30
_POLL_INTERVAL_S = 5
# HF cold builds are slower than Vercel; the worst-case empirical observation
# during Bundle H testing was ~90s for BUILDING. 10min gives plenty of headroom.
_RUN_POLL_TIMEOUT_S = 600


class HFSpacesError(RuntimeError):
    pass


def _headers() -> dict[str, str]:
    s = get_settings()
    return {"Authorization": f"Bearer {s.HF_TOKEN.get_secret_value()}"}


@retry(
    reraise=True,
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=4),
    retry=retry_if_exception_type((httpx.TransportError,)),
)
def _request(method: str, path: str, *, json: dict | None = None) -> httpx.Response:
    return httpx.request(
        method,
        f"{API}{path}",
        headers=_headers(),
        json=json,
        timeout=_TIMEOUT_S,
    )


def create_space(name: str, *, sdk: str = "gradio") -> dict[str, Any]:
    """Create a public Space under HF_USERNAME. Returns the API response.

    SDK must be one of HF's supported values: gradio | streamlit | docker |
    static. Bundle H uses gradio for ai_generator + ai_agent.
    """
    s = get_settings()
    if not s.HF_USERNAME:
        raise HFSpacesError("HF_USERNAME not set; cannot create Space")
    payload: dict[str, Any] = {
        "name": name,
        "type": "space",
        "sdk": sdk,
        "private": False,
        # organization=None means the personal account. If an org is added
        # later, pass it here.
    }
    r = _request("POST", "/api/repos/create", json=payload)
    if r.status_code not in (200, 201):
        raise HFSpacesError(
            f"create_space {name}: HTTP {r.status_code}: {r.text[:400]}"
        )
    return r.json()


def get_space(name: str) -> dict[str, Any] | None:
    """Return Space metadata (incl. runtime.stage), or None if not found."""
    s = get_settings()
    r = _request("GET", f"/api/spaces/{s.HF_USERNAME}/{name}")
    if r.status_code == 404:
        return None
    if r.status_code != 200:
        raise HFSpacesError(f"get_space {name}: HTTP {r.status_code}: {r.text[:300]}")
    return r.json()


def delete_space(name: str) -> None:
    """Delete a Space. Used by retire.py during rotation.

    Bundle H finding: HF's delete API wants the namespace in `organization`
    (works for both users and orgs) and the bare repo name in `name`. The
    `name='ns/repo'` shape that some HF clients use returns 403 with
    fine-grained tokens; the explicit organization key works.
    """
    s = get_settings()
    payload = {"name": name, "organization": s.HF_USERNAME, "type": "space"}
    r = _request("DELETE", "/api/repos/delete", json=payload)
    if r.status_code not in (200, 204):
        raise HFSpacesError(
            f"delete_space {name}: HTTP {r.status_code}: {r.text[:300]}"
        )


def push_url_with_token(name: str) -> str:
    """One-shot HTTPS URL with token embedded for `git push`.

    Use only as the URL argument to `git push`; never persist to .git/config.
    Pattern mirrors clients/github.py:push_url_with_token.
    """
    s = get_settings()
    token = s.HF_TOKEN.get_secret_value()
    return f"https://{s.HF_USERNAME}:{token}@huggingface.co/spaces/{s.HF_USERNAME}/{name}"


def public_url(name: str) -> str:
    """The public-facing Space URL. Empty string if HF_USERNAME is unset.

    HF rewrites dots in repo names to dashes in the public URL but doesn't
    touch dashes. The name_generator output (adjective-noun-number) is
    already dash-separated and lowercase, so no rewrite is needed.
    """
    s = get_settings()
    if not s.HF_USERNAME or not name:
        return ""
    return f"https://{s.HF_USERNAME}-{name}.hf.space"


def wait_for_running(name: str, *, timeout_s: int = _RUN_POLL_TIMEOUT_S) -> str:
    """Poll until Space reaches RUNNING. Returns the public URL.

    Raises HFSpacesError on BUILD_ERROR / RUNTIME_ERROR / CONFIG_ERROR;
    TimeoutError on timeout.
    """
    deadline = time.monotonic() + timeout_s
    last_stage: str | None = None
    while time.monotonic() < deadline:
        meta = get_space(name)
        if meta is None:
            raise HFSpacesError(f"Space {name} disappeared mid-deploy")
        stage = (meta.get("runtime") or {}).get("stage")
        if stage != last_stage:
            log.info("hf_spaces %s stage=%s", name, stage)
            last_stage = stage
        if stage == "RUNNING":
            return public_url(name)
        if stage in ("BUILD_ERROR", "RUNTIME_ERROR", "CONFIG_ERROR"):
            msg = (meta.get("runtime") or {}).get("errorMessage") or "(no errorMessage)"
            raise HFSpacesError(f"space {name} failed at stage {stage}: {msg[:500]}")
        time.sleep(_POLL_INTERVAL_S)
    raise TimeoutError(f"space {name} did not reach RUNNING within {timeout_s}s")


