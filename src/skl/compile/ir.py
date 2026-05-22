"""Compile-time intermediate representation.

A :class:`ResolvedSkill` is what every per-platform compiler reads. Build it
once per skill via :func:`build_ir`; per-platform compilers consume the same
IR. Construction is deterministic - the parsed Skill carries the raw text
verbatim, so compilers that do text-surgery (Skills-native frontmatter strip,
Identity body removal) preserve author formatting outside the bits they
deliberately rewrite.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from skl.sidecars import Sidecars, parse_sidecars
from skl.skill_md import Skill, parse_skill_md


@dataclass(frozen=True)
class ResolvedSkill:
    """One skill, ready to compile.

    ``skill`` is the parsed SKILL.md (frontmatter + body sections + raw text).
    ``sidecars`` holds every ``skl/platforms/<id>.yaml`` under the skill root,
    keyed by platform ID. ``skill_root`` and ``repo_root`` are absolute paths
    used to compute output locations and the provenance comment.
    """

    skill_root: Path
    repo_root: Path
    skill: Skill
    sidecars: Sidecars

    @property
    def name(self) -> str:
        """The skill's kebab name - SKILL.md ``name`` if set, else the folder name."""
        return self.skill.name or self.skill_root.name

    @property
    def source_skill_md(self) -> Path:
        """Absolute path to the source SKILL.md file."""
        return self.skill_root / "SKILL.md"

    @property
    def source_relpath(self) -> Path:
        """Source SKILL.md path relative to the repo root - used in the provenance comment."""
        return self.source_skill_md.relative_to(self.repo_root)


@dataclass
class CompileResult:
    """Outcome of compiling one (skill, platform) pair."""

    skill_name: str
    platform_id: str
    output_root: Path
    files_written: list[Path] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def build_ir(skill_root: Path, repo_root: Path) -> ResolvedSkill:
    """Parse SKILL.md + sidecars at ``skill_root`` into a :class:`ResolvedSkill`.

    Raises :class:`skl.skill_md.SkillParseError` for a malformed SKILL.md and
    :class:`skl.sidecars.SidecarParseError` for a malformed sidecar; callers
    typically run ``skl validate`` first, so these are exceptional.
    """
    skill_md = skill_root / "SKILL.md"
    skill = parse_skill_md(skill_md)
    sidecars = parse_sidecars(skill_root)
    return ResolvedSkill(
        skill_root=skill_root,
        repo_root=repo_root,
        skill=skill,
        sidecars=sidecars,
    )
