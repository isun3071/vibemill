"""Static analysis for generated slot files.

Hard policy gate over a small set of safety patterns: code-injection vectors,
process spawning, raw filesystem and socket access. See SECURITY.md.

Rules 11 (no runtime fetching) and 12 (no persistent storage) were removed
in ANTI_PATTERNS.md v5; flaky `fetch()`, `localStorage`, `sessionStorage`,
and database client imports are no longer blocked. Broken or flaky network
paths and ad-hoc client storage are on-brand for the genre.

Bundle H: per-language pattern sets. JS patterns scan .ts/.tsx/.js/.jsx;
Python patterns scan .py. Non-code files (requirements.txt, README.md,
.gitignore, .css) are skipped. The dispatch is by file extension; the
default for unknown extensions is the JS set (no Python false positives).

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

# JS / TS forbidden patterns. Code-injection vectors, Node process /
# filesystem APIs, raw socket APIs. Universal across the JS-substrate
# archetypes (tracker, chatbot, utility_tool, search_directory, etc.).
SUSPICIOUS_PATTERNS_JS: tuple[str, ...] = (
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

# Python forbidden patterns. Bundle H. Code-injection vectors, process
# spawning, deserialization of attacker-controlled data, dynamic import.
SUSPICIOUS_PATTERNS_PYTHON: tuple[str, ...] = (
    # Code-injection vectors
    r"\beval\s*\(",
    r"\bexec\s*\(",
    r"\b__import__\s*\(",
    r"\bcompile\s*\(",

    # Process spawning
    r"\bos\.system\b",
    r"\bos\.popen\b",
    r"\bsubprocess\.",

    # Deserialization of attacker-controlled data
    r"\bpickle\.loads\b",
    r"\bmarshal\.loads\b",
)

_COMPILED_JS: tuple[tuple[re.Pattern[str], str], ...] = tuple(
    (re.compile(p), p) for p in SUSPICIOUS_PATTERNS_JS
)
_COMPILED_PYTHON: tuple[tuple[re.Pattern[str], str], ...] = tuple(
    (re.compile(p), p) for p in SUSPICIOUS_PATTERNS_PYTHON
)

# Files that don't get scanned (not code, or chassis-controlled).
_SKIP_EXTENSIONS: frozenset[str] = frozenset({".css", ".txt", ".md", ".gitignore"})
_SKIP_BASENAMES: frozenset[str] = frozenset({
    "requirements.txt", "README.md", ".gitignore", "package.json",
    "tsconfig.json", "tailwind.config.ts", "postcss.config.js", "next.config.js",
})


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


def _patterns_for(path: str) -> tuple[tuple[re.Pattern[str], str], ...]:
    """Pick the pattern set for `path` by extension. .py uses Python set;
    .ts/.tsx/.js/.jsx use JS set. Other extensions return ()."""
    p = path.lower()
    if p.endswith(".py"):
        return _COMPILED_PYTHON
    if p.endswith((".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs")):
        return _COMPILED_JS
    return ()


def _should_skip(path: str) -> bool:
    p = path.lower()
    base = p.rsplit("/", 1)[-1]
    if base in _SKIP_BASENAMES:
        return True
    for ext in _SKIP_EXTENSIONS:
        if p.endswith(ext):
            return True
    return False


def static_analysis(slot_files: dict[str, str]) -> StaticAnalysisResult:
    """Scan the slot files for forbidden patterns.

    `slot_files` keys are file paths (e.g. 'app/page.tsx', 'lib/data.ts',
    'app.py') used to dispatch pattern set and to label diagnostics.
    Returns StaticAnalysisResult with safe=True or with details of the
    first match. We return on first match (no need to enumerate all).
    """
    for path, content in slot_files.items():
        if _should_skip(path):
            continue
        patterns = _patterns_for(path)
        if not patterns:
            # Unknown extension — fall back to JS patterns. Safer to scan
            # than to skip silently.
            patterns = _COMPILED_JS
        for compiled, raw_pattern in patterns:
            m = compiled.search(content)
            if m:
                return StaticAnalysisResult(
                    safe=False,
                    pattern=raw_pattern,
                    matched_text=m.group(0),
                    file_path=path,
                )
    return StaticAnalysisResult(safe=True, pattern=None, matched_text=None, file_path=None)
