"""Skills-native compiler: claude-code, claude-cowork, ms-cowork.

All three targets are Anthropic-Skills consumers; compile is essentially a
filesystem copy (SKL-006). The output is byte-identical across the three
platforms - only the destination path under ``platforms/<id>/<skill>/``
differs. One implementation here serves all three.

Transformations applied to the source SKILL.md:

1. **Strip the ``skl:`` frontmatter block.** Per SKL-006, toolkit scaffolding
   does not ship in compiled artefacts. Implemented via text surgery so the
   non-``skl`` frontmatter retains its original formatting (comments,
   indentation, key order).
2. **Strip the ``## Identity`` body section.** Per SKL-008, Claude-family
   surfaces already have Claude as the persona; the authored persona is
   noise. Implemented via text surgery so the rest of the body keeps its
   spacing.
3. **Prepend the provenance comment.** Per SKL-006, every compiled artefact
   leads with a ``# Compiled by skl <version> from <source> on <date>`` line.

Sibling folders are copied verbatim: ``references/``, ``scripts/``, ``assets/``
under the skill root land at the same relative paths under the output root.
``skl/`` (sidecars) and ``tests/`` (fixtures) are not copied - they are
authoring concerns, not part of the consumed artefact.
"""

from __future__ import annotations

import re
import shutil
from datetime import date
from pathlib import Path

from skl.compile.ir import CompileResult, ResolvedSkill
from skl.compile.provenance import provenance_comment

SKILLS_NATIVE_PLATFORMS: frozenset[str] = frozenset({"claude-code", "claude-cowork", "ms-cowork"})

# Sibling folders copied verbatim into the output root.
_SIBLING_COPY_DIRS: tuple[str, ...] = ("references", "scripts", "assets")

_FENCE_RE = re.compile(r"\A(---\s*\n)(.*?\n)(---\s*\n?)", re.DOTALL)
_H2_LINE_RE = re.compile(r"^## (.+?)\s*$")


def compile_skills_native(
    ir: ResolvedSkill,
    platform_id: str,
    *,
    now: date | None = None,
) -> CompileResult:
    """Compile ``ir`` for a Skills-native ``platform_id``.

    ``now`` is forwarded to :func:`provenance_comment` for deterministic
    tests; in normal use it defaults to today's date.
    """
    if platform_id not in SKILLS_NATIVE_PLATFORMS:
        raise ValueError(
            f"compile_skills_native called with non-Skills-native "
            f"platform {platform_id!r}; expected one of "
            f"{sorted(SKILLS_NATIVE_PLATFORMS)}"
        )

    output_root = ir.repo_root / "platforms" / platform_id / ir.name
    files_written = emit_skills_native(ir, output_root, now=now)

    return CompileResult(
        skill_name=ir.name,
        platform_id=platform_id,
        output_root=output_root,
        files_written=files_written,
    )


def emit_skills_native(
    ir: ResolvedSkill,
    output_root: Path,
    *,
    now: date | None = None,
) -> list[Path]:
    """Write the Skills-native artefact (compiled SKILL.md + siblings) to ``output_root``.

    Returns the list of files written. The output bytes are deterministic
    given the same IR and ``now`` - any caller that needs the Skills-native
    transformations (the dispatcher's main path, or the VS Code Skill
    variant in :mod:`skl.compile.vscode`) routes through here.
    """
    output_root.mkdir(parents=True, exist_ok=True)
    compiled_text = _build_compiled_skill_md(ir, now=now)
    output_skill_md = output_root / "SKILL.md"
    output_skill_md.write_text(compiled_text)
    files_written: list[Path] = [output_skill_md]
    for sibling_name in _SIBLING_COPY_DIRS:
        src = ir.skill_root / sibling_name
        if not src.is_dir():
            continue
        dst = output_root / sibling_name
        if dst.exists():
            shutil.rmtree(dst)
        shutil.copytree(src, dst)
        files_written.extend(sorted(p for p in dst.rglob("*") if p.is_file()))
    return files_written


# ---------------------------------------------------------------------------
# Text transformations
# ---------------------------------------------------------------------------


def _build_compiled_skill_md(ir: ResolvedSkill, *, now: date | None = None) -> str:
    """Apply SKL-006 / SKL-008 transformations and return the compiled file text."""
    raw = ir.skill.raw_text
    fence_match = _FENCE_RE.match(raw)
    if fence_match is None:
        raise ValueError(
            f"source {ir.source_skill_md} has no YAML frontmatter fence; "
            "this should have been caught by `skl validate` before compile"
        )
    open_fence = fence_match.group(1)
    fm_text = fence_match.group(2)
    close_fence = fence_match.group(3)
    body = raw[fence_match.end() :]

    fm_text = _remove_top_level_yaml_block(fm_text, "skl")
    body = _remove_h2_section(body, "Identity")

    prov = provenance_comment(ir.source_relpath, now=now)
    return f"{prov}\n{open_fence}{fm_text}{close_fence}{body}"


def _remove_top_level_yaml_block(fm_text: str, key: str) -> str:
    """Remove a top-level YAML mapping by its key (and all indented children).

    Detects the key as a line at column 0 matching ``<key>:``. Children are
    consecutive indented or blank lines; the block ends at the next column-0
    non-blank line (the next top-level key) or end-of-frontmatter. If the
    key is not found, the text is returned unchanged.
    """
    lines = fm_text.splitlines(keepends=True)
    key_re = re.compile(rf"^{re.escape(key)}\s*:")
    start: int | None = None
    end = len(lines)
    for i, line in enumerate(lines):
        if key_re.match(line):
            start = i
            break
    if start is None:
        return fm_text
    for i in range(start + 1, len(lines)):
        line = lines[i]
        if line.strip() == "":
            continue
        if not line.startswith((" ", "\t")):
            end = i
            break
    return "".join(lines[:start] + lines[end:])


def _remove_h2_section(body: str, name: str) -> str:
    """Remove an H2 section by heading (case-insensitive).

    The section is removed from the ``## Name`` line through (but not
    including) the next H2 line, or end-of-body. H2 lines inside fenced code
    blocks are not treated as section starts. If the section is not found,
    the body is returned unchanged.
    """
    target = name.lower().strip()
    lines = body.splitlines(keepends=True)
    in_code = False
    start: int | None = None
    end: int | None = None
    for i, line in enumerate(lines):
        if line.lstrip().startswith("```"):
            in_code = not in_code
            continue
        if in_code:
            continue
        match = _H2_LINE_RE.match(line)
        if not match:
            continue
        heading = match.group(1).strip().lower()
        if start is None and heading == target:
            start = i
        elif start is not None:
            end = i
            break
    if start is None:
        return body
    if end is None:
        end = len(lines)
    return "".join(lines[:start] + lines[end:])
