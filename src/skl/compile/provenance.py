"""Provenance comment used at the top of every compiled artefact (SKL-006).

The line carries the ``skl`` version, the source-relative path the artefact
was compiled from, and the compile date in ISO-8601. ``now`` and ``version``
are parameters so tests can pin them and assert byte-identical output.

The placement convention is per-target:

- SKILL.md (Skills-native targets): the comment sits above the ``---``
  frontmatter fence (SKL-006). Note: this means standard
  frontmatter-parsing tools that require ``---`` on line 1 will not find
  the fence; the trade-off is intentional (the compiled artefact is not
  a valid source SKILL.md by design - see SKL-006's reverse-trip-footgun
  rationale).
- JSON targets (M365 declarative-agent manifest, Stage 4): emitted as a
  sibling line / ``$comment`` field where the schema allows.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path

from skl import __version__


def provenance_comment(
    source_relpath: Path,
    *,
    now: date | None = None,
    version: str | None = None,
) -> str:
    """Return the SKL-006 provenance line (no trailing newline).

    ``source_relpath`` is the path to the source SKILL.md relative to the
    repo root - the compiled artefact is traceable to it without git context.
    ``now`` defaults to today's date (UTC); ``version`` defaults to the
    installed ``skl`` version.
    """
    v = version or __version__
    d = (now or datetime.now(UTC).date()).strftime("%Y-%m-%d")
    return f"# Compiled by skl {v} from {source_relpath} on {d}"
