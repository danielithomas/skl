"""VS Code compiler: Skill variant + Custom Agent variant (SKL-007).

Two emitted artefacts per skill, governed by whether
``<skill>/skl/platforms/vscode.yaml`` exists and what it declares:

| Sidecar     | `emit_skill` | Skill variant | Custom Agent variant |
|-------------|--------------|---------------|----------------------|
| absent      | n/a          | yes           | no                   |
| present     | `true` / -   | yes           | yes                  |
| present     | `false`      | no            | yes                  |

The **Skill variant** is byte-identical to the Skills-native compilers'
output for ``claude-code`` (per SKL-006), only written to
``platforms/vscode/skill/<name>/`` instead of ``platforms/claude-code/<name>/``.
Persona is stripped (per SKL-008). The implementation reuses
:func:`skl.compile.skills_native.emit_skills_native`.

The **Custom Agent variant** is a single ``.agent.md`` file at
``platforms/vscode/agent/<name>.agent.md``. The frontmatter is composed
fresh from the master SKILL.md + sidecar per SKL-007's mapping; the body
is the source SKILL.md body verbatim (Identity retained, per SKL-008).
The provenance comment sits above the frontmatter fence (per SKL-006).

``.chatmode.md`` is never emitted (per SKL-007's risk-table call).
"""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path
from typing import Any

from skl import manifest
from skl.compile.ir import CompileResult, ResolvedSkill
from skl.compile.provenance import provenance_comment
from skl.compile.skills_native import emit_skills_native

VSCODE_PLATFORM = "vscode"

# Sidecar fields that pass through verbatim to the Custom Agent frontmatter.
_PASSTHROUGH_FIELDS: tuple[str, ...] = (
    "target",
    "model",
    "agents",
    "handoffs",
    "hooks",
    "mcp-servers",
    "argument-hint",
    "user-invocable",
    "disable-model-invocation",
)

_FENCE_RE = re.compile(r"\A(---\s*\n)(.*?\n)(---\s*\n?)", re.DOTALL)


def compile_vscode(
    ir: ResolvedSkill,
    *,
    now: date | None = None,
) -> CompileResult:
    """Compile ``ir`` for VS Code. May emit one or both variants per SKL-007.

    The result's ``output_root`` is the ``platforms/vscode/`` directory
    (parent of both variants' subfolders). ``files_written`` enumerates
    every file produced across the variants.
    """
    sidecar_obj = ir.sidecars.get(VSCODE_PLATFORM)
    sidecar_data: dict[str, Any] = sidecar_obj.data if sidecar_obj is not None else {}
    emit_skill = sidecar_data.get("emit_skill", True)

    vscode_root = ir.repo_root / "platforms" / "vscode"
    files_written: list[Path] = []

    if emit_skill:
        skill_output_root = vscode_root / "skill" / ir.name
        files_written.extend(emit_skills_native(ir, skill_output_root, now=now))

    if sidecar_obj is not None:
        agent_dir = vscode_root / "agent"
        agent_dir.mkdir(parents=True, exist_ok=True)
        agent_path = agent_dir / f"{ir.name}.agent.md"
        agent_path.write_text(_build_custom_agent_md(ir, sidecar_data, now=now))
        files_written.append(agent_path)

    return CompileResult(
        skill_name=ir.name,
        platform_id=VSCODE_PLATFORM,
        output_root=vscode_root,
        files_written=files_written,
    )


# ---------------------------------------------------------------------------
# Custom Agent variant
# ---------------------------------------------------------------------------


def _build_custom_agent_md(
    ir: ResolvedSkill,
    sidecar_data: dict[str, Any],
    *,
    now: date | None = None,
) -> str:
    """Compose the ``.agent.md`` file contents.

    Layout (per SKL-006 + SKL-007):

    - Line 1: provenance comment.
    - Lines 2..N: composed Custom Agent frontmatter inside ``---`` fences.
    - Remaining: the source SKILL.md body verbatim (Identity retained
      per SKL-008's Custom-Agent-surface persona default).
    """
    raw = ir.skill.raw_text
    fence_match = _FENCE_RE.match(raw)
    if fence_match is None:
        raise ValueError(
            f"source {ir.source_skill_md} has no YAML frontmatter fence; "
            "this should have been caught by `skl validate` before compile"
        )
    body = raw[fence_match.end() :]

    frontmatter = _compose_custom_agent_frontmatter(ir, sidecar_data)
    frontmatter_yaml = manifest.dumps(frontmatter)

    prov = provenance_comment(ir.source_relpath, now=now)
    return f"{prov}\n---\n{frontmatter_yaml}---\n{body}"


def _compose_custom_agent_frontmatter(
    ir: ResolvedSkill,
    sidecar_data: dict[str, Any],
) -> dict[str, Any]:
    """Build the Custom Agent frontmatter dict per SKL-007's mapping table.

    Fields included only when set in the source / sidecar - the output is
    intentionally minimal so authors see only what they declared.
    """
    fm: dict[str, Any] = {"name": ir.name}
    if ir.skill.description:
        fm["description"] = ir.skill.description

    for key in _PASSTHROUGH_FIELDS:
        if key in sidecar_data:
            fm[key] = sidecar_data[key]

    tools = _compose_tools_list(sidecar_data)
    if tools:
        fm["tools"] = tools

    return fm


def _compose_tools_list(sidecar_data: dict[str, Any]) -> list[str]:
    """Build the Custom Agent ``tools`` array per SKL-007.

    Values from ``bindings.tools`` (sorted by skill tool ID for determinism)
    come first, then any explicit ``tools:`` entries in the sidecar (preserving
    declaration order). Duplicates are dropped while preserving first
    occurrence.
    """
    bindings = sidecar_data.get("bindings") or {}
    bindings_tools = bindings.get("tools") if isinstance(bindings, dict) else None
    bound_values: list[str] = []
    if isinstance(bindings_tools, dict):
        for skill_tool_id in sorted(bindings_tools):
            value = bindings_tools[skill_tool_id]
            if isinstance(value, str):
                bound_values.append(value)

    explicit = sidecar_data.get("tools") or []
    explicit_list = [item for item in explicit if isinstance(item, str)]

    result: list[str] = []
    seen: set[str] = set()
    for item in bound_values + explicit_list:
        if item not in seen:
            result.append(item)
            seen.add(item)
    return result
