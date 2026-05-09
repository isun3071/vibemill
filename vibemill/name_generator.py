"""Subdomain name generator: adjective-noun-NNNN.

The format matches the convention shown in the docs (e.g. 'melancholy-ferret-2847').
Used as the Vercel project name and the GitHub repo name. With ~50 adjectives,
~50 nouns, and a 4-digit suffix, collisions are statistically negligible at
V0 cadence (~5 apps/day).

The mood is mildly off-key by design: the adjectives lean melancholic,
bureaucratic, or absurd, never aspirational. Nouns are concrete, specific.
The names are not meant to be cute. They are inventory tags.
"""

from __future__ import annotations

import secrets

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


def make_name() -> str:
    """Return a fresh adjective-noun-NNNN identifier.

    Uses `secrets` rather than `random` so two separate processes generating
    names at the same moment do not converge on the same value (relevant for
    tests that run in parallel and for quick manual runs).
    """
    adj = secrets.choice(ADJECTIVES)
    noun = secrets.choice(NOUNS)
    suffix = secrets.randbelow(10_000)
    return f"{adj}-{noun}-{suffix:04d}"
