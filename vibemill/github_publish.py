"""GitHub publisher: create repo, fabricate a vibecoder commit history, push.

Per ANTI_PATTERNS.md rule 7, the commit history's progressive shift from
'initial commit' to 'i don't know what this code does' is part of the bit.
Do not normalize the messages. The chaos is the satirical payload.

Spec (Bundle K story-fidelity pass):
- Commit count is tier-driven: slop 2-3, mean_good 5-7, banger 9-14
- Author derived from the slug: melancholy-ferret-2847 ->
  name 'melancholy-ferret', email 'melancholy.ferret@vibemill.local'
- Timestamp window is tier-driven: slop 8-12h, mean_good 18-30h,
  banger 30-48h. Last commit lands at push_time. First commit lands
  at (push_time - window). Intermediate commits drawn uniformly.
- File additions are progressive across commits. The required file
  (app.py / app/page.tsx) lands in commit 0 with requirements.txt /
  package.json / .env.example if present. Remaining files distributed
  across commits 1..N-2. README.md + mlh.md land only in the LAST
  commit (real hackathon teams write the pitch artifact at the end).
- Subsequent commits also randomly tweak one line in a slot file. The
  tweak path is substrate-aware: nextjs bumps Tailwind class numbers,
  flask bumps CSS px values or appends comments to templates / app.py,
  gradio appends comments to app.py.
- Messages drawn (with replacement) from four pools:
  COHERENT_FIRST (1, first) + MIDDLE_COHERENT (variable)
  + LOSING_THE_THREAD (variable) + LATE (1, last) = count
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
from .models import SUBSTRATE_BY_ARCHETYPE, GeneratedFile

log = logging.getLogger(__name__)


COHERENT_FIRST: tuple[str, ...] = (
    "initial commit",
    "add basic structure",
    "first version",
    "setup project",
    "scaffold",
    "boilerplate",
)

# Bundle K: archetype-agnostic. Works for trackers, chatbots, todos,
# games, marketplaces, etc. Avoid stack-specific words ("chart", "tracker",
# "tailwind") that only fit one archetype.
MIDDLE_COHERENT: tuple[str, ...] = (
    "wire up the form",
    "actually save to db",
    "add the routes",
    "fix the layout",
    "tweak the colors",
    "rename the variable",
    "make it actually work",
    "css pass",
    "padding fixes",
    "add the login",
    "wire up auth",
    "fix the redirect",
    "handle the empty state",
    "add the placeholder data",
    "real seed data now",
    "actually return json",
    "clean up the imports",
    "trim that helper",
    "small refactor",
    "polish the buttons",
    "spacing",
    "fix the form submit",
    "add the page",
    "wire up the api call",
    "hide that error",
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
    "what is going on",
    "trying something",
    "back to before",
    "no wait this",
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
    "demo time",
    "readme",
    "writeup",
    "submission",
)

VIBE_COMMENTS_JS: tuple[str, ...] = (
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

VIBE_COMMENTS_PY: tuple[str, ...] = (
    "# works",
    "# hmm",
    "# tweak",
    "# adjust",
    "# fix later",
    "# good enough",
    "# not sure why",
    "# trying",
    "# recheck this",
    "# nudge",
    "# idk",
)

VIBE_COMMENTS_HTML: tuple[str, ...] = (
    "<!-- works -->",
    "<!-- hmm -->",
    "<!-- tweak -->",
    "<!-- fix later -->",
    "<!-- good enough -->",
    "<!-- not sure why -->",
    "<!-- nudge -->",
    "<!-- idk -->",
)

# Tailwind: bg-blue-500, p-4, text-gray-700, gap-2 (rounded-md excluded — no number)
_TAILWIND_RE = re.compile(r"\b(bg|text|border|ring|p|m|px|py|mx|my|gap|rounded)-(\w+-)?(\d+)\b")

# CSS pixel values: "padding: 16px", "margin-left:8px"
_CSS_PX_RE = re.compile(r":\s*(\d+)px\b")

# Files Vibe Mill always treats as "late-stage authoring": real teams
# write the pitch artifact at the end of the hackathon, not the start.
LATE_STAGE_BASENAMES: frozenset[str] = frozenset({"README.md", "mlh.md"})

# Tier-driven commit count windows. (min, max) inclusive.
_COMMIT_COUNT_BY_TIER: dict[str, tuple[int, int]] = {
    "slop": (2, 3),
    "mean_good": (5, 7),
    "banger": (9, 14),
}

# Tier-driven timestamp windows in minutes. (min, max) inclusive.
# slop 8-12h, mean_good 18-30h, banger 30-48h.
_WINDOW_MINUTES_BY_TIER: dict[str, tuple[int, int]] = {
    "slop": (480, 720),
    "mean_good": (1080, 1800),
    "banger": (1800, 2880),
}


def _required_path_for_stack(stack: str) -> str:
    return {"nextjs": "app/page.tsx"}.get(stack, "app.py")


def _initial_bucket_basenames(stack: str) -> frozenset[str]:
    """Files that join commit 0 alongside the required path. Stack-aware so
    the first commit looks like the moment 'we set up the project'."""
    if stack == "nextjs":
        return frozenset({"app/page.tsx", "lib/data.ts", "package.json"})
    return frozenset({"app.py", "requirements.txt", ".env.example"})


@dataclass
class CommitPlan:
    message: str
    timestamp: datetime


@dataclass
class PublishResult:
    html_url: str
    last_commit_sha: str
    commit_count: int
    # GitHub's numeric repository id, needed by Vercel's POST /v13/deployments
    # gitSource.repoId field. Returned by GitHub's POST /orgs/{org}/repos as
    # response.id; we just pass it through.
    repo_id: int


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


def _commit_count_for_tier(tier: str | None) -> int:
    """Random commit count drawn from the tier's range."""
    lo, hi = _COMMIT_COUNT_BY_TIER.get(tier or "mean_good", _COMMIT_COUNT_BY_TIER["mean_good"])
    return lo + secrets.randbelow(hi - lo + 1)


def _split_message_buckets(count: int) -> tuple[int, int]:
    """Return (middle_count, losing_count) with 1 + middle + losing + 1 == count.
    Bundle K: scales with tier. Roughly 30-40% losing-the-thread for longer
    histories; 0-1 for slop. Always at least 1 middle when count > 2."""
    if count <= 2:
        # slop: just first + last (or first alone)
        return 0, 0
    if count == 3:
        return 1, 0
    # 30-40% losing the thread, rounded
    interior = count - 2
    losing = max(0, min(interior - 1, int(round(interior * 0.35))))
    middle = interior - losing
    return middle, losing


def _draw_messages(count: int) -> list[str]:
    if count <= 0:
        return []
    if count == 1:
        return [secrets.choice(COHERENT_FIRST)]
    middle_n, losing_n = _split_message_buckets(count)
    msgs = [secrets.choice(COHERENT_FIRST)]
    msgs.extend(secrets.choice(MIDDLE_COHERENT) for _ in range(middle_n))
    msgs.extend(secrets.choice(LOSING_THE_THREAD) for _ in range(losing_n))
    msgs.append(secrets.choice(LATE))
    assert len(msgs) == count
    return msgs


def _generate_timestamps(
    count: int, push_time: datetime, tier: str | None = None,
) -> list[datetime]:
    """Tier-driven timestamp layout. First commit lands at (push_time - window);
    last commit lands at push_time. Intermediates drawn uniformly within the
    window so the cadence has natural-looking gaps."""
    if count == 1:
        return [push_time]
    lo, hi = _WINDOW_MINUTES_BY_TIER.get(tier or "mean_good", _WINDOW_MINUTES_BY_TIER["mean_good"])
    window_min = lo + secrets.randbelow(hi - lo + 1)
    window_s = window_min * 60
    intermediate = sorted(secrets.randbelow(window_s - 1) + 1 for _ in range(count - 2))
    positions_s = [0] + intermediate + [window_s]
    t_first = push_time - timedelta(seconds=window_s)
    return [t_first + timedelta(seconds=p) for p in positions_s]


def _apply_random_modification(src: Path, stack: str) -> None:
    """Tweak one line in one slot file, substrate-aware. nextjs: Tailwind class
    number bump or JS comment append. flask: CSS px tweak, HTML comment append,
    or Python comment append. gradio: Python comment append.

    The vibecoder did not do surgical edits; neither do we.
    """
    if stack == "nextjs":
        _tweak_nextjs(src)
    elif stack == "flask":
        _tweak_flask(src)
    elif stack == "gradio":
        _tweak_gradio(src)


def _list_files_with_ext(src: Path, ext: str) -> list[Path]:
    return [p for p in src.rglob(f"*{ext}") if p.is_file() and ".git" not in p.parts]


def _append_comment(target: Path, pool: tuple[str, ...]) -> None:
    text = target.read_text()
    if not text.endswith("\n"):
        text += "\n"
    text += secrets.choice(pool) + "\n"
    target.write_text(text)


def _tweak_nextjs(src: Path) -> None:
    candidates = [src / rel for rel in ("app/page.tsx", "lib/data.ts") if (src / rel).is_file()]
    if not candidates:
        return
    target = candidates[secrets.randbelow(len(candidates))]
    text = target.read_text()
    if secrets.randbelow(2) == 0:
        match = _TAILWIND_RE.search(text)
        if match:
            old_n = int(match.group(3))
            delta = (100 if old_n >= 100 else 1) * (1 if secrets.randbelow(2) == 0 else -1)
            new_n = max(0, old_n + delta) or old_n + abs(delta)
            old_class = match.group(0)
            new_class = old_class[: match.start(3) - match.start(0)] + str(new_n)
            target.write_text(text.replace(old_class, new_class, 1))
            return
    _append_comment(target, VIBE_COMMENTS_JS)


def _tweak_flask(src: Path) -> None:
    """Pick from app.py, templates/*.html, or static/*.css. CSS px tweak if
    matchable; otherwise comment append in the appropriate syntax."""
    candidates: list[tuple[Path, str]] = []
    app_py = src / "app.py"
    if app_py.is_file():
        candidates.append((app_py, "py"))
    for p in _list_files_with_ext(src, ".html"):
        candidates.append((p, "html"))
    for p in _list_files_with_ext(src, ".css"):
        candidates.append((p, "css"))
    if not candidates:
        return
    target, kind = candidates[secrets.randbelow(len(candidates))]
    if kind == "css":
        text = target.read_text()
        match = _CSS_PX_RE.search(text)
        if match:
            old_n = int(match.group(1))
            delta = 2 if secrets.randbelow(2) == 0 else -2
            new_n = max(0, old_n + delta) or old_n + abs(delta)
            old_chunk = match.group(0)
            new_chunk = old_chunk.replace(str(old_n), str(new_n), 1)
            target.write_text(text.replace(old_chunk, new_chunk, 1))
            return
        # CSS fall-through: append /* comment */
        _append_comment(target, tuple(f"/* {c.strip('# ')} */" for c in VIBE_COMMENTS_PY))
        return
    if kind == "html":
        _append_comment(target, VIBE_COMMENTS_HTML)
        return
    _append_comment(target, VIBE_COMMENTS_PY)


def _tweak_gradio(src: Path) -> None:
    target = src / "app.py"
    if not target.is_file():
        return
    _append_comment(target, VIBE_COMMENTS_PY)


def _distribute_files(
    files: list[GeneratedFile],
    *,
    commit_count: int,
    stack: str,
) -> list[list[GeneratedFile]]:
    """Split LLM-produced files into commit_count buckets.

    Bucket 0 gets the required path plus stack-baseline files
    (requirements.txt or package.json, .env.example, lib/data.ts).
    Remaining files spread roughly evenly across buckets 1..N-2.
    Bucket N-1 (final) gets any leftover plus README + mlh (handled by
    the caller). Empty middle buckets are fine; the random-mod step
    fills them with a one-line tweak diff.
    """
    if commit_count <= 0:
        return []
    initial = _initial_bucket_basenames(stack)
    bucket_zero = [f for f in files if f.path in initial]
    remaining = [f for f in files if f.path not in initial]
    if commit_count == 1:
        return [bucket_zero + remaining]

    buckets: list[list[GeneratedFile]] = [bucket_zero]
    middle_slots = commit_count - 1
    if not remaining:
        buckets.extend([] for _ in range(middle_slots))
        return buckets

    per = max(1, len(remaining) // middle_slots)
    cursor = 0
    for b in range(middle_slots - 1):
        buckets.append(remaining[cursor : cursor + per])
        cursor += per
    buckets.append(remaining[cursor:])  # final commit absorbs leftover
    return buckets


def _write_bucket(src: Path, bucket: list[GeneratedFile]) -> None:
    for f in bucket:
        out = src / f.path
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(f.content)


def _stash_distributable_files(
    src: Path,
    files: list[GeneratedFile],
) -> tuple[dict[str, str], dict[str, str]]:
    """Pull the LLM-produced files and the late-stage files (README/mlh) out
    of `src` so the initial commit only contains the chassis. Returns
    (llm_content, late_content) for restoration during the commit loop."""
    llm_content: dict[str, str] = {}
    for f in files:
        p = src / f.path
        if p.exists():
            llm_content[f.path] = p.read_text()
            p.unlink()
    late_content: dict[str, str] = {}
    for name in LATE_STAGE_BASENAMES:
        p = src / name
        if p.exists():
            late_content[name] = p.read_text()
            p.unlink()
    return llm_content, late_content


def _build_history(
    src: Path,
    *,
    actor: Actor,
    plans: list[CommitPlan],
    files: list[GeneratedFile],
    late_content: dict[str, str],
    stack: str,
) -> str:
    """Initialize a git repo at `src` and create commits per `plans`, with
    progressive file additions and random tweaks. Returns the SHA of the
    last commit.
    """
    repo = Repo.init(src, initial_branch="main")
    buckets = _distribute_files(files, commit_count=len(plans), stack=stack)
    last_sha = ""
    for i, plan in enumerate(plans):
        # Write this commit's bucket of LLM-produced files.
        if i < len(buckets):
            _write_bucket(src, buckets[i])
        # Random one-line tweak on commits after the first (a no-op if there's
        # nothing to tweak, e.g. early commit with no slot files yet).
        if i > 0:
            _apply_random_modification(src, stack)
        # Final commit: write README + mlh (real teams write the pitch late).
        if i == len(plans) - 1:
            for name, content in late_content.items():
                (src / name).write_text(content)
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
    files: list[GeneratedFile],
    archetype: str,
    tier: str | None = None,
    push_time: datetime | None = None,
) -> PublishResult:
    """Create the GitHub repo, build a tier-shaped vibecoder commit history
    at `src`, push, return the public URL and last commit SHA.

    `files` is the LLM-produced file set (gen_out.files). Used to distribute
    files across commits progressively rather than dumping them all in
    commit 0. `tier` and `archetype` drive count, timestamp window, and
    substrate-aware tweak patterns.

    `push_time` defaults to now (UTC). Override only for deterministic tests.
    """
    if push_time is None:
        push_time = datetime.now(timezone.utc)

    repo_data = github.create_repo(name, description=description)
    log.info("github_publish: created repo %s", repo_data.get("html_url"))

    author_name, author_email = derive_author(name)
    actor = Actor(author_name, author_email)

    stack = SUBSTRATE_BY_ARCHETYPE.get(archetype, "nextjs")
    count = _commit_count_for_tier(tier)
    messages = _draw_messages(count)
    timestamps = _generate_timestamps(count, push_time, tier)
    plans = [CommitPlan(message=m, timestamp=t) for m, t in zip(messages, timestamps)]

    # Stash distributable + late-stage content so the chassis is alone in
    # the working tree before commit 0. _build_history will restore.
    _, late_content = _stash_distributable_files(src, files)

    log.info(
        "github_publish: %s history plan: %d commits, tier=%s stack=%s window=%s author=%s",
        name, count, tier, stack,
        (timestamps[-1] - timestamps[0]) if count > 1 else "0s",
        author_name,
    )
    for p in plans:
        log.info("  %s  %s", p.timestamp.isoformat(), p.message)

    last_sha = _build_history(
        src, actor=actor, plans=plans, files=files,
        late_content=late_content, stack=stack,
    )

    push_url = github.push_url_with_token(name)
    Repo(src).git.push(push_url, "HEAD:main")
    log.info("github_publish: pushed %s (%d commits, last=%s)", name, count, last_sha[:7])
    return PublishResult(
        html_url=repo_data.get("html_url", github.repo_https_url(name)),
        last_commit_sha=last_sha,
        commit_count=count,
        repo_id=int(repo_data["id"]),
    )
