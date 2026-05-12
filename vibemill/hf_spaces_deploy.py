"""HF Spaces deploy stage. Bundle H.

Sibling to vercel_deploy.py for the Next.js rail. Workflow for a Python
archetype (ai_generator, ai_agent):

1. Create the Space via the HF API.
2. Force-push the local git repo (already has the vibecoder commit history
   from github_publish.publish) to the Space remote.
3. Poll the Space's runtime stage until RUNNING.
4. Return the public URL.

Force push: the freshly-created Space contains an auto-generated README we
don't want; our chassis README has the correct SDK + Python pins (per the
Bundle H test findings). The vibecoder history wins.

Per OPERATIONS.md, the deploy stage's failure is recorded as
death_cause='never_built' and the GitHub repo is archived; the orchestrator
already handles that branch via the vercel_deploy timeout path.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from git import Repo

from .clients import hf_spaces

log = logging.getLogger(__name__)


@dataclass
class HFDeployResult:
    space_name: str
    public_url: str


def create_and_push(*, name: str, src: Path) -> HFDeployResult:
    """Create a Gradio Space and push the local working directory to it.

    `src` must be a directory that already has files staged (chassis +
    LLM-produced slots) AND a git history (github_publish builds the
    vibecoder commit history before this step). We add the HF remote and
    force-push that history.

    Does NOT wait for the Space to reach RUNNING; call wait_for_running
    separately so the orchestrator can sequence the screenshot pass.
    """
    if not (src / ".git").is_dir():
        raise RuntimeError(
            f"hf_spaces_deploy: {src} has no .git; "
            "github_publish.publish must run before this step"
        )
    space = hf_spaces.create_space(name, sdk="gradio")
    log.info("hf_spaces_deploy: created space %s -> %s", name, space.get("url"))

    push_url = hf_spaces.push_url_with_token(name)
    repo = Repo(src)
    repo.git.push("--force", push_url, "HEAD:main")
    log.info("hf_spaces_deploy: force-pushed %s to hf space", name)

    return HFDeployResult(space_name=name, public_url=hf_spaces.public_url(name))


def wait_for_url(name: str, *, timeout_s: int = 600) -> HFDeployResult:
    """Block until the Space is RUNNING. Returns the live URL."""
    url = hf_spaces.wait_for_running(name, timeout_s=timeout_s)
    log.info("hf_spaces_deploy: %s ready at %s", name, url)
    return HFDeployResult(space_name=name, public_url=url)
