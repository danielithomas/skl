"""Implementation of ``skl lint``.

Style enforcement for SKILL.md and sidecar source files. The rule set
codifies the bans documented in CLAUDE.md / D-008:

- ``em-dash`` / ``en-dash`` - the em-dash (U+2014) and en-dash (U+2013)
  characters are banned (per CLAUDE.md / D-010 follow-up). Auto-fixable
  to `` - ``.
- ``au-spelling`` - US spellings are flagged; AU equivalents suggested.
  Auto-fixable.
- ``credentials`` - high-signal regex patterns for AWS / Anthropic /
  OpenAI / GitHub / Slack tokens and generic ``BEGIN PRIVATE KEY``
  markers. Not auto-fixable - the author must remove the credential.
- ``unresolved-token`` - ``{{variables.X}}`` references where X is not
  declared in the skill's ``skl.variables[]``. Validate (Check 7) errors
  on the same condition; lint warns to give authors a heads-up in
  in-progress edits.
- ``banned-phrase`` - ``"as an AI"``, ``"I cannot fulfill"``,
  ``"in order to"`` and similar AI-ese; rejected per CLAUDE.md /
  Australian-English writing conventions.

Rule severity: ``error`` for credentials and en/em-dashes (CLAUDE.md
explicit ban); ``warning`` for spellings, banned phrases, and unresolved
tokens (style / heads-up).

Files scanned: ``*.md``, ``*.yaml``, ``*.yml``, ``*.txt`` under each
skill folder. Compiled artefacts under ``platforms/`` are skipped (they
are derived from source and inherit the source's lint posture).
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from skl.skill_md import SkillParseError, parse_skill_md

Severity = Literal["error", "warning"]


@dataclass
class LintFinding:
    """One flagged location in a source file.

    Auto-fixable findings carry ``fix`` as a ``(search, replace)`` tuple:
    :func:`apply_fixes` runs ``str.replace(search, replace, 1)`` on the
    file content. One-at-a-time replacement composes cleanly when multiple
    findings target the same line (each consumes its own match).
    """

    rule: str
    severity: Severity
    file: Path
    line: int
    message: str
    fix: tuple[str, str] | None = None


@dataclass
class LintReport:
    """All findings for a lint run."""

    findings: list[LintFinding] = field(default_factory=list)

    @property
    def errors(self) -> list[LintFinding]:
        return [f for f in self.findings if f.severity == "error"]

    @property
    def warnings(self) -> list[LintFinding]:
        return [f for f in self.findings if f.severity == "warning"]

    @property
    def has_errors(self) -> bool:
        return bool(self.errors)


# ---------------------------------------------------------------------------
# Rule data
# ---------------------------------------------------------------------------

# US -> AU spelling pairs. Small focused set for v0.1; the lint kit in
# `_shared/lint/` will eventually carry the canonical list.
_US_TO_AU: tuple[tuple[str, str], ...] = (
    ("organize", "organise"),
    ("organized", "organised"),
    ("organizing", "organising"),
    ("organization", "organisation"),
    ("organizations", "organisations"),
    ("realize", "realise"),
    ("realized", "realised"),
    ("realizing", "realising"),
    ("realization", "realisation"),
    ("recognize", "recognise"),
    ("recognized", "recognised"),
    ("recognizing", "recognising"),
    ("optimize", "optimise"),
    ("optimized", "optimised"),
    ("optimizing", "optimising"),
    ("optimization", "optimisation"),
    ("optimizations", "optimisations"),
    ("color", "colour"),
    ("colored", "coloured"),
    ("colors", "colours"),
    ("behavior", "behaviour"),
    ("behaviors", "behaviours"),
    ("center", "centre"),
    ("centered", "centred"),
    ("centers", "centres"),
    ("favor", "favour"),
    ("favored", "favoured"),
    ("favors", "favours"),
    ("favorite", "favourite"),
    ("favorites", "favourites"),
    ("catalog", "catalogue"),
    ("cataloged", "catalogued"),
    ("catalogs", "catalogues"),
    ("license", "licence"),  # noun only; verb is "license" in AU too - false positive accepted
    ("traveling", "travelling"),
    ("traveled", "travelled"),
    ("specialize", "specialise"),
    ("specialized", "specialised"),
    ("modeling", "modelling"),
    ("modeled", "modelled"),
)

# High-signal credential patterns. Anchored where possible to keep false-positives low.
_CREDENTIAL_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("aws-access-key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("anthropic-api-key", re.compile(r"\bsk-ant-(api\d+-)?[A-Za-z0-9\-_]{20,}\b")),
    ("openai-api-key", re.compile(r"\bsk-[A-Za-z0-9]{20,}\b")),
    ("github-pat", re.compile(r"\bghp_[A-Za-z0-9]{36}\b")),
    ("gitlab-pat", re.compile(r"\bglpat-[A-Za-z0-9\-_]{20}\b")),
    ("slack-token", re.compile(r"\bxox[bpsa]-[A-Za-z0-9\-]{10,}\b")),
    ("private-key-block", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
)

# Banned phrases (case-insensitive). The replacement is left to the author.
_BANNED_PHRASES: tuple[str, ...] = (
    "as an AI",
    "I cannot fulfill",
    "I cannot fulfil",
    "in order to",
)

# Files we lint (extensions relative to a skill folder).
_LINT_EXTENSIONS: frozenset[str] = frozenset({".md", ".yaml", ".yml", ".txt"})

# Subfolders that hold compiled output - skipped (derived from source).
_SKIP_DIRS: frozenset[str] = frozenset({"platforms"})

_DASH_RE = re.compile("[—–]")  # em-dash + en-dash
_TOKEN_RE = re.compile(r"\{\{\s*variables\.([a-z][a-z0-9_]*)\s*\}\}")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def lint_repo(repo_root: Path) -> LintReport:
    """Lint every skill in ``<repo_root>/skills/``."""
    report = LintReport()
    skills_dir = repo_root / "skills"
    if not skills_dir.is_dir():
        return report
    for skill_md in sorted(skills_dir.glob("*/SKILL.md")):
        sub = lint_skill(skill_md.parent)
        report.findings.extend(sub.findings)
    return report


def lint_skill(skill_root: Path) -> LintReport:
    """Lint a single skill folder."""
    report = LintReport()
    declared_variables = _declared_variables(skill_root)
    for path in _files_to_lint(skill_root):
        text = path.read_text()
        for finding in _lint_text(text, path, declared_variables):
            report.findings.append(finding)
    return report


def apply_fixes(findings: list[LintFinding]) -> set[Path]:
    """Apply every fixable finding in place. Returns the set of files modified.

    Findings without a ``fix`` are skipped. Each fix is applied once via
    ``str.replace(search, replace, 1)``, so multiple findings with the
    same ``(search, replace)`` pair walk through consecutive matches in
    the file - no overlap handling needed.
    """
    modified: set[Path] = set()
    by_file: dict[Path, list[LintFinding]] = {}
    for finding in findings:
        if finding.fix is None:
            continue
        by_file.setdefault(finding.file, []).append(finding)
    for path, file_findings in by_file.items():
        original = path.read_text()
        updated = original
        for finding in file_findings:
            assert finding.fix is not None
            search, replace = finding.fix
            updated = updated.replace(search, replace, 1)
        if updated != original:
            path.write_text(updated)
            modified.add(path)
    return modified


# ---------------------------------------------------------------------------
# Per-file linting
# ---------------------------------------------------------------------------


def _files_to_lint(skill_root: Path) -> Iterator[Path]:
    """Yield ``*.md`` / ``*.yaml`` / ``*.yml`` / ``*.txt`` files in the skill folder."""
    for path in sorted(skill_root.rglob("*")):
        if not path.is_file():
            continue
        if path.suffix not in _LINT_EXTENSIONS:
            continue
        relative_parts = path.relative_to(skill_root).parts
        # Only the *top-level* `platforms/` dir is the compiled-output dir.
        # The nested `skl/platforms/` directory holds sidecars and IS linted.
        if relative_parts and relative_parts[0] in _SKIP_DIRS:
            continue
        yield path


def _declared_variables(skill_root: Path) -> set[str]:
    """Return the variable names declared in ``SKILL.md``'s ``skl.variables[]``.

    Best-effort: if the SKILL.md fails to parse, return an empty set (the
    unresolved-token rule degrades to flagging every reference, but that
    is recoverable - the user fixes the frontmatter, then re-runs lint).
    """
    skill_md = skill_root / "SKILL.md"
    if not skill_md.is_file():
        return set()
    try:
        skill = parse_skill_md(skill_md)
    except SkillParseError:
        return set()
    return set(skill.variable_names)


def _lint_text(text: str, path: Path, declared_variables: set[str]) -> Iterator[LintFinding]:
    """Apply every rule against the file's text, line by line."""
    for line_num, raw_line in enumerate(text.splitlines(keepends=True), start=1):
        yield from _check_em_dash(raw_line, path, line_num)
        yield from _check_au_spelling(raw_line, path, line_num)
        yield from _check_credentials(raw_line, path, line_num)
        yield from _check_banned_phrases(raw_line, path, line_num)
        yield from _check_unresolved_tokens(raw_line, path, line_num, declared_variables)


def _check_em_dash(line: str, path: Path, line_num: int) -> Iterator[LintFinding]:
    """Emit one finding per dash character; each fix replaces one dash."""
    for match in _DASH_RE.finditer(line):
        char = match.group(0)
        yield LintFinding(
            rule="em-dash",
            severity="error",
            file=path,
            line=line_num,
            message=f"{char!r} detected; use ' - ' (space-hyphen-space) instead",
            fix=(char, " - "),
        )


def _check_au_spelling(line: str, path: Path, line_num: int) -> Iterator[LintFinding]:
    """Emit one finding per US-spelled word, with a case-preserving fix."""
    for us, au in _US_TO_AU:
        pattern = re.compile(rf"\b{re.escape(us)}\b", re.IGNORECASE)
        for match in pattern.finditer(line):
            actual = match.group(0)
            replacement = _match_case(actual, au)
            yield LintFinding(
                rule="au-spelling",
                severity="warning",
                file=path,
                line=line_num,
                message=f"US spelling {actual!r}; use AU {replacement!r}",
                fix=(actual, replacement),
            )


def _match_case(original: str, replacement: str) -> str:
    """Apply original's case (upper / title / lower) to the replacement."""
    if original.isupper():
        return replacement.upper()
    if original[:1].isupper():
        return replacement[:1].upper() + replacement[1:]
    return replacement


def _check_credentials(line: str, path: Path, line_num: int) -> Iterator[LintFinding]:
    for rule_name, pattern in _CREDENTIAL_PATTERNS:
        if pattern.search(line):
            yield LintFinding(
                rule=f"credentials/{rule_name}",
                severity="error",
                file=path,
                line=line_num,
                message=(
                    f"possible {rule_name} credential detected; do not commit secrets - "
                    "move to the configured secrets backend (per D-008)"
                ),
            )


def _check_banned_phrases(line: str, path: Path, line_num: int) -> Iterator[LintFinding]:
    lower = line.lower()
    for phrase in _BANNED_PHRASES:
        if phrase.lower() in lower:
            yield LintFinding(
                rule="banned-phrase",
                severity="warning",
                file=path,
                line=line_num,
                message=f"banned phrase {phrase!r}; rewrite to avoid AI-ese (per CLAUDE.md)",
            )


def _check_unresolved_tokens(
    line: str, path: Path, line_num: int, declared_variables: set[str]
) -> Iterator[LintFinding]:
    for match in _TOKEN_RE.finditer(line):
        var_name = match.group(1)
        if var_name not in declared_variables:
            yield LintFinding(
                rule="unresolved-token",
                severity="warning",
                file=path,
                line=line_num,
                message=(
                    f"`{{{{variables.{var_name}}}}}` is not declared in "
                    "`skl.variables[]` (run `skl validate` for the strict check)"
                ),
            )
