"""Subdomain name generator.

Two naming modes, sampled per-app:

- **inventory** (1 in 5): adjective-noun-NNNN, e.g. 'melancholy-ferret-2847'.
  Mood is mildly off-key by design: melancholic, bureaucratic, absurd.
  These look like placeholder names a real vibecoder leaves on a project
  they couldn't be bothered to name (the "untitled-12" register).

- **descriptive** (4 in 5): 2-4 word kebab-case derived by Haiku from the
  source headline + archetype, e.g. 'hanta-tracker', 'hormuz-watch'.
  These look like names a real vibecoder gives to a project they actually
  thought about for ten seconds.

Real vibecoders use both. Sampling across the distribution is faithful to
ANTI_PATTERNS rule 5 v4 (sample real-producer variance, don't flatten).

Used as the Vercel project name and the GitHub repo name. _ensure_unique
checks the local SQLite for collisions and appends -2, -3, ... if needed.
"""

from __future__ import annotations

import logging
import re
import secrets
from typing import TYPE_CHECKING

from .clients import openrouter
from .config import get_settings

if TYPE_CHECKING:
    pass

log = logging.getLogger(__name__)

INVENTORY_RATE_DENOMINATOR = 5  # 1 in 5 picks land in inventory mode

# 2-4 words, lowercase ASCII letters/digits, hyphen-separated.
_DESCRIPTIVE_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+){1,3}$")
_NAME_PROMPT_FILE = "name.txt"
_NAME_MAX_TOKENS = 30


ADJECTIVES: tuple[str, ...] = (
    "melancholy",
    "exhausted",
    "indifferent",
    "haunted",
    "perfunctory",
    "wistful",
    "redundant",
    "obsolete",
    "vestigial",
    "spurious",
    "tepid",
    "incidental",
    "provisional",
    "marginal",
    "auxiliary",
    "interim",
    "errant",
    "negligent",
    "derelict",
    "subordinate",
    "ambient",
    "dormant",
    "fallible",
    "unremarkable",
    "ordinary",
    "literal",
    "approximate",
    "tentative",
    "discontinued",
    "deprecated",
    "embargoed",
    "redacted",
    "footnoted",
    "amended",
    "restated",
    "reissued",
    "withdrawn",
    "miscatalogued",
    "unattributed",
    "anonymous",
    "verbose",
    "laconic",
    "deferred",
    "unscheduled",
    "unverified",
    "unaudited",
    "uninspected",
    "uncertified",
    "untested",
    "unsalvaged",
)

NOUNS: tuple[str, ...] = (
    "ferret",
    "crow",
    "moth",
    "vole",
    "newt",
    "shrew",
    "marmot",
    "raccoon",
    "tapir",
    "civet",
    "ledger",
    "memo",
    "addendum",
    "errata",
    "appendix",
    "footnote",
    "bibliography",
    "index",
    "glossary",
    "preface",
    "spreadsheet",
    "envelope",
    "receipt",
    "voucher",
    "permit",
    "form",
    "filing",
    "deposition",
    "affidavit",
    "disclosure",
    "kiosk",
    "vestibule",
    "annex",
    "atrium",
    "lobby",
    "corridor",
    "stairwell",
    "mezzanine",
    "rotunda",
    "antechamber",
    "trolley",
    "dolly",
    "pallet",
    "crate",
    "carton",
    "manifest",
    "inventory",
    "shipment",
    "consignment",
    "dispatch",
)


def make_inventory_name() -> str:
    """Return a fresh adjective-noun-NNNN identifier.

    Uses `secrets` rather than `random` so two separate processes generating
    names at the same moment do not converge on the same value.
    """
    adj = secrets.choice(ADJECTIVES)
    noun = secrets.choice(NOUNS)
    suffix = secrets.randbelow(10_000)
    return f"{adj}-{noun}-{suffix:04d}"


def _load_name_prompt() -> str:
    return (get_settings().prompts_dir / _NAME_PROMPT_FILE).read_text()


def make_descriptive_name(
    archetype: str,
    source_summary: str,
    source_headline: str,
) -> str | None:
    """One Haiku call (t=0.7) for a 2-4 word kebab-case project name.

    Returns the name on success, or None if the LLM output failed format
    validation. Caller falls back to inventory mode on None.
    """
    user_prompt = (
        _load_name_prompt()
        .replace("{{archetype}}", archetype or "tracker")
        .replace("{{source_headline}}", source_headline or "")
        .replace("{{source_summary}}", source_summary or "")
    )
    try:
        completion = openrouter.complete(
            model=get_settings().GUARD_MODEL,  # haiku, locked per rotation policy
            messages=[{"role": "user", "content": user_prompt}],
            purpose="name",
            temperature=0.7,
            reasoning_effort="disabled",
            max_tokens=_NAME_MAX_TOKENS,
        )
    except Exception as exc:
        log.warning("descriptive name LLM call failed: %s", exc)
        return None

    raw = (completion.text or "").strip().lower()
    # Strip surrounding quotes/backticks the LLM sometimes adds despite the prompt.
    raw = raw.strip("\"'`")
    # If the LLM emitted prose, take only the first line.
    raw = raw.splitlines()[0].strip() if raw else ""
    if not _DESCRIPTIVE_RE.match(raw):
        log.warning("descriptive name failed format validation: %r", raw)
        return None
    return raw


def _ensure_unique(name: str) -> str:
    """Append -2, -3, ... up to -99 if the name collides with an existing app
    in SQLite. Beyond that, append a 4-hex-char fallback (essentially never
    reached at V0 cadence)."""
    from . import db  # local import: db is heavy and may import models that import this
    if db.get_app(name) is None:
        return name
    for n in range(2, 100):
        candidate = f"{name}-{n}"
        if db.get_app(candidate) is None:
            log.info("name collision on %s, using %s", name, candidate)
            return candidate
    fallback = f"{name}-{secrets.token_hex(2)}"
    log.warning("name collision on %s and -2..-99; falling back to %s", name, fallback)
    return fallback


def make_name(
    *,
    archetype: str = "tracker",
    source_headline: str = "",
    source_summary: str = "",
) -> str:
    """Roll between inventory mode (1 in 5) and descriptive mode (4 in 5).

    Inventory mode does not need source context. Descriptive mode does — if
    no headline is supplied, the router falls through to inventory mode
    regardless of the roll.
    """
    use_inventory = (
        not source_headline
        or secrets.randbelow(INVENTORY_RATE_DENOMINATOR) == 0
    )
    if use_inventory:
        candidate = make_inventory_name()
    else:
        candidate = make_descriptive_name(
            archetype=archetype,
            source_summary=source_summary,
            source_headline=source_headline,
        )
        if candidate is None:
            candidate = make_inventory_name()
    return _ensure_unique(candidate)
