"""Copilot Studio compiler.

Output: ``platforms/copilot-studio/instructions.md`` - a single markdown
file pasted into Copilot Studio's free-text instructions field.

Compilation behaviour (per ``docs/spec/compilation.md`` and the
skills-spec analysis §8.3):

- Body composed in canonical order:
  Identity + Tone (inlined; no H2 headers in output) -> Capabilities ->
  Knowledge Sources -> Tools -> Workflow -> Output Format ->
  Response Templates -> Edge Cases -> Examples. Sections missing from
  the source are skipped.
- ``{{knowledge.<id>}}`` and ``{{tools.<id>}}`` tokens are rewritten to
  ``/<binding-value>`` Copilot Studio UI references when the sidecar
  declares a string binding for that ID. Variable tokens
  (``{{variables.x}}``) are left as-is for deploy-time substitution
  (per D-007).
- Persona surfaces by default (per SKL-008): Identity stays in.
- 8,000-character hard budget enforced on the instructions body
  (provenance line excluded). The sidecar's ``budget:`` field can
  lower the cap (per the platform schema).
- Provenance comment per SKL-006 sits as the first line of the file.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from skl.compile._transforms import rewrite_binding_tokens
from skl.compile.budget import enforce_budget
from skl.compile.ir import CompileResult, ResolvedSkill
from skl.compile.provenance import provenance_comment
from skl.skill_md import Skill

COPILOT_STUDIO_PLATFORM = "copilot-studio"

# Sections rendered after the inlined Identity+Tone preamble, in order.
# Any section not present in the source is skipped (no empty headers).
_SECTION_ORDER: tuple[str, ...] = (
    "Capabilities",
    "Knowledge Sources",
    "Tools",
    "Workflow",
    "Output Format",
    "Response Templates",
    "Edge Cases",
    "Examples",
)


def compile_copilot_studio(
    ir: ResolvedSkill,
    *,
    now: date | None = None,
) -> CompileResult:
    """Compile ``ir`` for Copilot Studio.

    Returns a :class:`CompileResult` pointing at
    ``platforms/copilot-studio/instructions.md``. Raises
    :class:`skl.compile.budget.BudgetExceededError` if the instructions
    body exceeds the 8K cap (or the sidecar's per-skill override).
    """
    sidecar = ir.sidecars.get(COPILOT_STUDIO_PLATFORM)
    sidecar_data: dict[str, Any] = sidecar.data if sidecar is not None else {}

    instructions = compose_copilot_studio_instructions(ir, sidecar_data=sidecar_data)

    override = sidecar_data.get("budget") if isinstance(sidecar_data, dict) else None
    enforce_budget(
        instructions,
        platform_id=COPILOT_STUDIO_PLATFORM,
        skill_name=ir.name,
        override=override,
    )

    output_root = ir.repo_root / "platforms" / "copilot-studio"
    output_root.mkdir(parents=True, exist_ok=True)
    output_path = output_root / "instructions.md"
    prov = provenance_comment(ir.source_relpath, now=now)
    output_path.write_text(f"{prov}\n\n{instructions}")

    return CompileResult(
        skill_name=ir.name,
        platform_id=COPILOT_STUDIO_PLATFORM,
        output_root=output_root,
        files_written=[output_path],
    )


def compose_copilot_studio_instructions(
    ir: ResolvedSkill,
    *,
    sidecar_data: dict[str, Any] | None = None,
) -> str:
    """Build the Copilot Studio instructions text (no provenance comment).

    Exposed so ``skl budget`` can measure the would-be instructions length
    without writing to disk.
    """
    if sidecar_data is None:
        sidecar = ir.sidecars.get(COPILOT_STUDIO_PLATFORM)
        sidecar_data = sidecar.data if sidecar is not None else {}

    bindings = sidecar_data.get("bindings") or {}
    knowledge_bindings = bindings.get("knowledge") or {}
    tool_bindings = bindings.get("tools") or {}

    parts: list[str] = []

    preamble = _compose_identity_tone(ir.skill)
    if preamble:
        parts.append(preamble)

    for section_name in _SECTION_ORDER:
        body = ir.skill.section(section_name)
        if body is None:
            continue
        body = body.strip()
        if not body:
            continue
        body = rewrite_binding_tokens(body, "knowledge", knowledge_bindings, prefix="/")
        body = rewrite_binding_tokens(body, "tools", tool_bindings, prefix="/")
        parts.append(f"## {section_name}\n\n{body}")

    return "\n\n".join(parts) + "\n"


def _compose_identity_tone(skill: Skill) -> str:
    """Inline ``## Identity`` and ``## Tone`` (if present) as the preamble.

    The H2 headers are dropped - the resulting paragraphs form the lead of
    the instructions text. SKL-008 keeps Identity surfaced for Copilot
    Studio; Tone is optional per the body-section convention.
    """
    chunks: list[str] = []
    for section_name in ("Identity", "Tone"):
        body = skill.section(section_name)
        if body is None:
            continue
        body = body.strip()
        if body:
            chunks.append(body)
    return "\n\n".join(chunks)
