"""Report character usage of compiled instructions versus per-platform caps.

Implementation entry point for ``skl budget``. Walks every skill in the
repo, computes the would-be compiled-instructions length for each
enabled platform that has a budget cap, and reports the numbers as a
deterministic table.

Only Copilot Studio and M365 have hard caps (per :data:`skl.compile.budget.PLATFORM_BUDGETS`).
The Skills-native and VS Code targets are uncapped and do not appear in
the report.

Determinism: same input set + same kit -> byte-identical output. Suitable
for CI drift detection if a skill grows over time.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from skl.compile.budget import PLATFORM_BUDGETS
from skl.compile.copilot_studio import (
    COPILOT_STUDIO_PLATFORM,
    compose_copilot_studio_instructions,
)
from skl.compile.ir import ResolvedSkill, build_ir
from skl.compile.m365 import M365_PLATFORM, compose_m365_instructions


@dataclass(frozen=True)
class BudgetRow:
    """One ``(skill, platform)`` budget measurement."""

    skill_name: str
    platform_id: str
    used: int
    cap: int

    @property
    def percent(self) -> float:
        if self.cap == 0:
            return 0.0
        return 100.0 * self.used / self.cap

    @property
    def over_budget(self) -> bool:
        return self.used > self.cap


@dataclass
class BudgetReport:
    """Aggregate of every measured (skill, platform) pair in the repo."""

    rows: list[BudgetRow] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    """Skill names whose budget could not be computed (parse error etc.)."""

    @property
    def has_overages(self) -> bool:
        return any(r.over_budget for r in self.rows)


def budget_report(repo_root: Path) -> BudgetReport:
    """Build a :class:`BudgetReport` for every budget-capped (skill, platform) pair."""
    report = BudgetReport()
    skills_dir = repo_root / "skills"
    if not skills_dir.is_dir():
        return report

    for skill_md in sorted(skills_dir.glob("*/SKILL.md")):
        skill_root = skill_md.parent
        try:
            ir = build_ir(skill_root, repo_root)
        except Exception:
            report.skipped.append(skill_root.name)
            continue
        for platform_id in ir.skill.enabled_platforms:
            if platform_id not in PLATFORM_BUDGETS:
                continue
            row = _measure(ir, platform_id)
            if row is not None:
                report.rows.append(row)
    return report


def render_report(report: BudgetReport) -> str:
    """Render the report as a single-string table for the CLI."""
    if not report.rows and not report.skipped:
        return "no skills with budget-enforced platforms found\n"

    lines: list[str] = []
    header = f"{'Skill':<30}  {'Platform':<15}  {'Used':>7}  {'Cap':>7}  {'%':>4}  Status"
    lines.append(header)
    lines.append("-" * len(header))
    for row in report.rows:
        status = "OVER" if row.over_budget else "ok"
        lines.append(
            f"{row.skill_name:<30}  "
            f"{row.platform_id:<15}  "
            f"{row.used:>7,}  "
            f"{row.cap:>7,}  "
            f"{row.percent:>3.0f}%  "
            f"{status}"
        )
    if report.skipped:
        lines.append("")
        lines.append(f"skipped (could not parse): {', '.join(sorted(report.skipped))}")
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Per-platform measurement
# ---------------------------------------------------------------------------


def _measure(ir: ResolvedSkill, platform_id: str) -> BudgetRow | None:
    """Compute the instructions length for one (skill, platform) pair.

    Returns ``None`` if composition errors (e.g. M365 schema-version
    resolution fails) - the failure surfaces clearly at compile time.
    """
    cap = PLATFORM_BUDGETS[platform_id]
    try:
        if platform_id == COPILOT_STUDIO_PLATFORM:
            text = compose_copilot_studio_instructions(ir)
            sidecar = ir.sidecars.get(COPILOT_STUDIO_PLATFORM)
            sidecar_data = sidecar.data if sidecar is not None else {}
            override = sidecar_data.get("budget") if isinstance(sidecar_data, dict) else None
            if isinstance(override, int) and override > 0:
                cap = override
        elif platform_id == M365_PLATFORM:
            text = compose_m365_instructions(ir)
        else:
            return None
    except Exception:
        return None

    return BudgetRow(
        skill_name=ir.name,
        platform_id=platform_id,
        used=len(text),
        cap=cap,
    )
