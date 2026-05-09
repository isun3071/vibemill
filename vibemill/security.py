"""Static analysis for generated slot files.

Hard policy gate per ANTI_PATTERNS.md rules 11 (no runtime data fetching)
and 12 (no persistent storage), plus the pre-existing safety patterns from
SECURITY.md (eval, child_process, etc.).

The static analysis runs after the verifier and before the build (per
GENERATOR.md v3 "Static analysis pass"). On match: app is stillborn with
death_cause='forbidden_pattern'. No retry. Forbidden patterns are policy
violations, not transient errors.

The verifier may incidentally fix a forbidden pattern (which is fine), but
the verifier prompt is not asked to check for them. This module is the
hard gate.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# Universal patterns: forbidden in every archetype.
SUSPICIOUS_PATTERNS_UNIVERSAL: tuple[str, ...] = (
    # Pre-existing safety patterns (SECURITY.md v1)
    r"\beval\s*\(",
    r"\bnew\s+Function\s*\(",
    r"\bchild_process\b",
    r"\bfs\.\w+",
    r"\brequire\s*\(\s*[\"']https?:",

    # Rule 11: runtime data fetching
    r"\bfetch\s*\(",
    r"\baxios\b",
    r"\bhttpx\b",
    r"\bgot\s*\(",
    r"\bnode-fetch\b",
    r"\bcheerio\b",
    r"\bjsdom\b",
    r"\bpuppeteer\b",
    r"\bplaywright\b",

    # Rule 12: persistent storage
    r"\bpg\b",
    r"\bmysql2?\b",
    r"@supabase/supabase-js",
    r"@vercel/kv",
    r"@vercel/postgres",
    r"better-sqlite3",
    r"\bprisma\b",
    r"@planetscale/database",
    r"\bneon-database\b",
    r"@neondatabase/serverless",

    # Forbidden node APIs
    r"\bnet\.",
    r"\bdgram\.",
    r"\btls\.",
    r"\bcrypto\.subtle",

    # Storage APIs forbidden in all archetypes (sessionStorage, cookie writes)
    r"\bsessionStorage\b",
    r"document\.cookie\s*=",
)

# Conditional pattern: localStorage is permitted ONLY for the glorified_todo
# archetype (per ANTI_PATTERNS.md rule 12). All other archetypes get the
# stillborn treatment if localStorage shows up.
_LOCAL_STORAGE_RE = re.compile(r"\blocalStorage\b")
_GLORIFIED_TODO = "glorified_todo"

# Compile once at module load.
_COMPILED_UNIVERSAL: tuple[tuple[re.Pattern[str], str], ...] = tuple(
    (re.compile(p), p) for p in SUSPICIOUS_PATTERNS_UNIVERSAL
)


@dataclass
class StaticAnalysisResult:
    safe: bool
    pattern: str | None  # the regex string that matched, if any
    matched_text: str | None  # the substring that matched, if any
    file_path: str | None  # which slot file matched

    @property
    def reason(self) -> str | None:
        if self.safe:
            return None
        return f"forbidden pattern {self.pattern!r} matched in {self.file_path}: {self.matched_text!r}"


def static_analysis(slot_files: dict[str, str], archetype: str) -> StaticAnalysisResult:
    """Scan the slot files for forbidden patterns.

    `slot_files` keys are file paths (e.g. 'app/page.tsx', 'lib/data.ts')
    used only for diagnostics. The function checks each file independently
    so the matched location is preserved in the result.

    Returns StaticAnalysisResult with safe=True or with details of the
    first match. We return on first match (no need to enumerate all).
    """
    for path, content in slot_files.items():
        for compiled, raw_pattern in _COMPILED_UNIVERSAL:
            m = compiled.search(content)
            if m:
                return StaticAnalysisResult(
                    safe=False,
                    pattern=raw_pattern,
                    matched_text=m.group(0),
                    file_path=path,
                )

        # Conditional: localStorage only allowed for glorified_todo.
        if archetype != _GLORIFIED_TODO:
            m = _LOCAL_STORAGE_RE.search(content)
            if m:
                return StaticAnalysisResult(
                    safe=False,
                    pattern=r"\blocalStorage\b",
                    matched_text=m.group(0),
                    file_path=path,
                )

    return StaticAnalysisResult(safe=True, pattern=None, matched_text=None, file_path=None)
