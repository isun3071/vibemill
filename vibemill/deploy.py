"""Deploy router.

Bundle H: the orchestrator no longer hardcodes vercel_deploy. This module
dispatches per archetype to the appropriate deploy backend:

- 'js' archetypes (tracker, chatbot, utility_tool, search_directory, etc.)
  -> vercel_deploy (Next.js on Vercel, existing path).
- 'python' archetypes (ai_generator, ai_agent) -> hf_spaces_deploy (Gradio
  on HF Spaces, new path).

The two backends have different shapes:
- Vercel needs the GitHub repo_id + commit sha. It pulls from GitHub.
- HF Spaces needs the local src directory. It force-pushes from disk.

The router takes both kinds of inputs and threads them to the right backend.
Returns a unified DeployOutcome so the orchestrator can record the same
shape regardless of substrate.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from . import hf_spaces_deploy, vercel_deploy
from .models import SUBSTRATE_BY_ARCHETYPE

log = logging.getLogger(__name__)

# Per ANTI_PATTERNS.md: not all substrates ship through Vercel. The string
# values mirror the deploy_target column in apps (migration 010).
DEPLOY_TARGET_VERCEL = "vercel"
DEPLOY_TARGET_HF_SPACES = "hf_spaces"


@dataclass
class DeployOutcome:
    deploy_target: str  # 'vercel' | 'hf_spaces'
    public_url: str     # the live URL
    project_name: str   # vercel project name or hf space name


def substrate_for(archetype: str) -> str:
    """Return 'js' or 'python' for an archetype, defaulting to 'js' for
    archetypes that haven't been classified yet."""
    return SUBSTRATE_BY_ARCHETYPE.get(archetype, "js")


def deploy(
    *,
    archetype: str,
    name: str,
    src_dir: Path,
    repo_id: int,
    commit_sha: str,
) -> DeployOutcome:
    """Dispatch to the right deploy backend. Blocks until the deploy is
    READY/RUNNING. Raises on terminal failure (caller marks app stillborn).
    """
    substrate = substrate_for(archetype)
    if substrate == "python":
        # HF Spaces: create + force-push from src_dir (already has the
        # vibecoder commit history from github_publish), then wait.
        hf_spaces_deploy.create_and_push(name=name, src=src_dir)
        result = hf_spaces_deploy.wait_for_url(name)
        log.info("deploy %s: hf_spaces ready at %s", name, result.public_url)
        return DeployOutcome(
            deploy_target=DEPLOY_TARGET_HF_SPACES,
            public_url=result.public_url,
            project_name=name,
        )

    # Default: Vercel rail (Next.js).
    vercel_deploy.create_project_for_repo(name, repo_id=repo_id, sha=commit_sha)
    result = vercel_deploy.wait_for_url(name)
    log.info("deploy %s: vercel ready at %s", name, result.public_url)
    return DeployOutcome(
        deploy_target=DEPLOY_TARGET_VERCEL,
        public_url=result.public_url,
        project_name=result.project_name,
    )
