"""GitHub publisher: create repo, fabricate a vibecoder commit history, push.

Per ANTI_PATTERNS.md rule 7, the commit history's progressive shift from
'initial commit' to 'i don't know what this code does' is part of the bit.
Do not normalize the messages. The chaos is the satirical payload.

Spec (per maintainer):
- 4-7 commits per app, randomized via secrets.randbelow(4) + 4
- Author derived from the slug. melancholy-ferret-2847 ->
  name 'melancholy-ferret', email 'melancholy.ferret@vibemill.local'
- First commit 2-4 hours before push time; intermediate commits spread
  across the window; last commit at push time
- Commit 1 adds all files. Subsequent commits modify a single line in a
  random slot file (a comment append or a Tailwind class number tweak).
  Diffs are NOT plausible; the vibecoder did not do real surgical edits.
- Messages drawn (with replacement) from four pools:
  COHERENT_FIRST (1, always first) + MIDDLE_COHERENT (2-4)
  + LOSING_THE_THREAD (0-2) + LATE (1, always last) = count
"""

from __future__ import annotations

import logging
import re
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from git import Actor, Repo

from .clients import github

log = logging.getLogger(__name__)


COHERENT_FIRST: tuple[str, ...] = (
    "initial commit",
    "add basic structure",
    "first version",
    "setup project",
)

MIDDLE_COHERENT: tuple[str, ...] = (
    "add tracker dashboard",
    "add data file",
    "hook up the chart",
    "styling pass",
    "add tailwind classes",
    "fix layout",
    "update colors",
    "adjust spacing",
    "refactor components",
    "add map panel",
)

LOSING_THE_THREAD: tuple[str, ...] = (
    "trying again",
    "another attempt",
    "fix the thing",
    "why doesn't this work",
    "undo last change",
    "revert",
    "hmm",
    "ok this should work now",
)

LATE: tuple[str, ...] = (
    "final",
    "final final",
    "actually final this time",
    "i give up",
    "good enough",
    "ship it",
    "please work",
    "i don't know what this code does",
    "whatever",
    "ok ship",
)

# Files the vibecoder touches during the iteration history. The chassis
# files are scaffolding the vibecoder did not write; we leave them alone.
TWEAKABLE_RELPATHS: tuple[str, ...] = (
    "app/page.tsx",
    "lib/data.ts",
)

VIBE_COMMENTS: tuple[str, ...] = (
    "// works",
    "// hmm",
    "// tweak",
    "// adjust",
    "// fix later",
    "// good enough",
    "// not sure why",
    "// trying",
    "// recheck this",
    "// nudge",
    "// idk",
)

# Matches Tailwind utility classes with a numeric suffix:
#   bg-blue-500, p-4, text-gray-700, gap-2, rounded-md (excluded; no number)
_TAILWIND_RE = re.compile(r"\b(bg|text|border|ring|p|m|px|py|mx|my|gap|rounded)-(\w+-)?(\d+)\b")


@dataclass
class CommitPlan:
    message: str
    timestamp: datetime


@dataclass
class PublishResult:
    html_url: str
    last_commit_sha: str
    commit_count: int


def derive_author(slug: str) -> tuple[str, str]:
    """melancholy-ferret-2847 -> ('melancholy-ferret', 'melancholy.ferret@vibemill.local').

    Drops the trailing all-digits piece if present. The .local TLD is reserved
    for local-only addresses and won't accidentally route mail.
    """
    parts = slug.split("-")
    if parts and parts[-1].isdigit():
        parts = parts[:-1]
    if not parts:
        parts = [slug]
    name = "-".join(parts)
    email_local = ".".join(parts)
    return name, f"{email_local}@vibemill.local"


def _split_message_buckets(count: int) -> tuple[int, int]:
    """Given a total commit count (4-7), return (middle_count, losing_count).

    Constraint: 1 + middle + losing + 1 == count, with middle in [2, 4]
    and losing in [0, 2]. The constraint is always satisfiable for 4 <= count <= 7.
    """
    middle_min = max(2, count - 4)  # losing <= 2 -> middle >= count - 4
    middle_max = min(4, count - 2)  # losing >= 0 -> middle <= count - 2
    span = middle_max - middle_min + 1
    middle = middle_min + secrets.randbelow(span)
    return middle, count - 2 - middle


def _draw_messages(count: int) -> list[str]:
    middle_n, losing_n = _split_message_buckets(count)
    msgs = [secrets.choice(COHERENT_FIRST)]
    msgs.extend(secrets.choice(MIDDLE_COHERENT) for _ in range(middle_n))
    msgs.extend(secrets.choice(LOSING_THE_THREAD) for _ in range(losing_n))
    msgs.append(secrets.choice(LATE))
    assert len(msgs) == count
    return msgs


def _generate_timestamps(count: int, push_time: datetime) -> list[datetime]:
    """Lay out commit timestamps so the first is 2-4 hours before push_time
    and the last lands exactly at push_time. Intermediate positions are
    drawn uniformly within the window.
    """
    if count == 1:
        return [push_time]
    window_min = secrets.randbelow(121) + 120  # 120-240 minutes = 2-4 hours
    window_s = window_min * 60
    intermediate = sorted(secrets.randbelow(window_s - 1) + 1 for _ in range(count - 2))
    positions_s = [0] + intermediate + [window_s]
    t_first = push_time - timedelta(seconds=window_s)
    return [t_first + timedelta(seconds=p) for p in positions_s]


def _apply_random_modification(src: Path) -> None:
    """Tweak one line in one slot file: comment append (50%) or Tailwind
    number bump (50%, with comment-append fallback if no Tailwind match).

    The vibecoder did not do surgical edits; neither do we.
    """
    candidates = [src / rel for rel in TWEAKABLE_RELPATHS if (src / rel).is_file()]
    if not candidates:
        return
    target = candidates[secrets.randbelow(len(candidates))]
    text = target.read_text()

    if secrets.randbelow(2) == 0:
        match = _TAILWIND_RE.search(text)
        if match:
            old_n = int(match.group(3))
            if old_n >= 100:
                delta = 100 if secrets.randbelow(2) == 0 else -100
                if old_n + delta < 0:
                    delta = -delta
            else:
                delta = 1 if secrets.randbelow(2) == 0 else -1
                if old_n + delta < 0:
                    delta = -delta
            new_n = old_n + delta
            old_class = match.group(0)
            new_class = old_class[: match.start(3) - match.start(0)] + str(new_n)
            text = text.replace(old_class, new_class, 1)
            target.write_text(text)
            return

    # Fall through: append a vibe comment.
    if not text.endswith("\n"):
        text += "\n"
    text += secrets.choice(VIBE_COMMENTS) + "\n"
    target.write_text(text)


def _build_history(
    src: Path,
    *,
    actor: Actor,
    plans: list[CommitPlan],
) -> str:
    """Initialize a git repo at `src` and create commits per `plans`.
    Returns the SHA of the last commit.
    """
    repo = Repo.init(src, initial_branch="main")
    last_sha = ""
    for i, plan in enumerate(plans):
        if i == 0:
            repo.git.add(A=True)
        else:
            _apply_random_modification(src)
            repo.git.add(A=True)
        # GitPython accepts ISO-8601 strings for author_date / commit_date.
        ts = plan.timestamp.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+0000")
        commit = repo.index.commit(
            plan.message,
            author=actor,
            committer=actor,
            author_date=ts,
            commit_date=ts,
        )
        last_sha = commit.hexsha
    return last_sha


def publish(
    *,
    name: str,
    description: str,
    src: Path,
    push_time: datetime | None = None,
) -> PublishResult:
    """Create the GitHub repo, build a vibecoder commit history at `src`,
    push, return the public URL and last commit SHA.

    `push_time` defaults to now (UTC). Override only for deterministic tests.
    """
    if push_time is None:
        push_time = datetime.now(timezone.utc)

    repo_data = github.create_repo(name, description=description)
    log.info("github_publish: created repo %s", repo_data.get("html_url"))

    author_name, author_email = derive_author(name)
    actor = Actor(author_name, author_email)

    count = secrets.randbelow(4) + 4  # 4-7
    messages = _draw_messages(count)
    timestamps = _generate_timestamps(count, push_time)
    plans = [CommitPlan(message=m, timestamp=t) for m, t in zip(messages, timestamps)]
    log.info(
        "github_publish: %s history plan: %d commits, author=%s",
        name, count, author_name,
    )
    for p in plans:
        log.info("  %s  %s", p.timestamp.isoformat(), p.message)

    last_sha = _build_history(src, actor=actor, plans=plans)

    push_url = github.push_url_with_token(name)
    Repo(src).git.push(push_url, "HEAD:main")
    log.info("github_publish: pushed %s (%d commits, last=%s)", name, count, last_sha[:7])
    return PublishResult(
        html_url=repo_data.get("html_url", github.repo_https_url(name)),
        last_commit_sha=last_sha,
        commit_count=count,
    )
