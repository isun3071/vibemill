"""Static analysis for generated slot files.

Hard policy gate over a small set of safety patterns: code-injection vectors,
process spawning, raw filesystem and socket access. See SECURITY.md.

Rules 11 (no runtime fetching) and 12 (no persistent storage) were removed
in ANTI_PATTERNS.md v5; flaky `fetch()`, `localStorage`, `sessionStorage`,
and database client imports are no longer blocked. Broken or flaky network
paths and ad-hoc client storage are on-brand for the genre.

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

# Forbidden in every archetype. Code-injection vectors, process / filesystem,
# raw socket APIs. See SECURITY.md.
SUSPICIOUS_PATTERNS_UNIVERSAL: tuple[str, ...] = (
    # Code-injection vectors
    r"\beval\s*\(",
    r"\bnew\s+Function\s*\(",
    r"\brequire\s*\(\s*[\"']https?:",

    # Process / filesystem
    r"\bchild_process\b",
    r"\bfs\.\w+",

    # Raw socket APIs
    r"\bnet\.",
    r"\bdgram\.",
    r"\btls\.",
    r"\bcrypto\.subtle",
)

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


def static_analysis(slot_files: dict[str, str]) -> StaticAnalysisResult:
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
    return StaticAnalysisResult(safe=True, pattern=None, matched_text=None, file_path=None)
