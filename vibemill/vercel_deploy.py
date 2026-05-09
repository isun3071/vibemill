"""Vercel deploy stage.

Wires the Vercel client to the orchestrator. Two responsibilities:
1. create_project_for_repo: link a Vercel project to the freshly-pushed
   GitHub repo. Vercel begins the first deployment automatically.
2. wait_for_url: poll until the first deployment is READY, return the
   public URL.

Per OPERATIONS.md, the deploy stage retries up to 3 times on transport
errors (the underlying client handles this) and times out after 5 minutes
of polling. On terminal failure, the orchestrator marks the app stillborn
with death_cause='never_built' and archives the GitHub repo.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from .clients import vercel
from .config import get_settings

log = logging.getLogger(__name__)


@dataclass
class DeployResult:
    project_id: str
    project_name: str
    public_url: str


def create_project_for_repo(name: str) -> dict:
    """Create the Vercel project linked to vibemill-apps/{name}. Returns
    the project record. Vercel auto-deploys on the first push to the
    linked repo's default branch.
    """
    s = get_settings()
    full_repo = f"{s.GITHUB_ORG}/{name}"
    project = vercel.create_project(name, full_repo)
    log.info("vercel_deploy: created project %s -> %s", project.get("id"), full_repo)
    return project


def wait_for_url(name: str, *, timeout_s: int = 300) -> DeployResult:
    """Poll for the project's first READY deployment. Returns the public URL."""
    deployment = vercel.wait_for_ready_deployment(name, timeout_s=timeout_s)
    project = vercel.get_project(name)
    if project is None:
        raise vercel.VercelError(f"project {name} disappeared mid-deploy")
    url = vercel.deployment_url(deployment)
    log.info("vercel_deploy: %s ready at %s", name, url)
    return DeployResult(
        project_id=project["id"],
        project_name=name,
        public_url=url,
    )
