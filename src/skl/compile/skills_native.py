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

import shutil
from datetime import date
from pathlib import Path

from skl.compile._transforms import (
    remove_h2_section,
    remove_top_level_yaml_block,
    split_frontmatter_and_body,
)
from skl.compile.ir import CompileResult, ResolvedSkill
from skl.compile.provenance import provenance_comment

SKILLS_NATIVE_PLATFORMS: frozenset[str] = frozenset({"claude-code", "claude-cowork", "ms-cowork"})

# Sibling folders copied verbatim into the output root.
_SIBLING_COPY_DIRS: tuple[str, ...] = ("references", "scripts", "assets")


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
    open_fence, fm_text, close_fence, body = split_frontmatter_and_body(ir.skill.raw_text)
    fm_text = remove_top_level_yaml_block(fm_text, "skl")
    body = remove_h2_section(body, "Identity")
    prov = provenance_comment(ir.source_relpath, now=now)
    return f"{prov}\n{open_fence}{fm_text}{close_fence}{body}"
