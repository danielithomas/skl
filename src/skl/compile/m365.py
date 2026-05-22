"""M365 declarative-agent compiler.

Outputs:

- ``platforms/m365/declarative-agent.json`` - the manifest. Validates
  against the bundled schema for the per-skill pinned ``schema_version``
  (per SKL-009).
- ``platforms/m365/instructions.md`` - the human-readable mirror of the
  manifest's ``instructions`` field (for diff / review). The manifest's
  ``instructions`` field carries the same text inline.

Compilation behaviour:

- Body composed in canonical order:
  Capabilities -> Knowledge Sources -> Tools -> Workflow ->
  Output Format -> Response Templates -> Edge Cases -> Examples.
  ``## Identity`` is **stripped** (per SKL-008's strip default for M365).
- ``{{knowledge.<id>}}`` and ``{{tools.<id>}}`` tokens rewrite to the
  binding value only when the sidecar declares a string binding. M365
  bindings are typically dicts (``{capability: ..., items_by_url: ...}``),
  in which case the token is left in place - the bindings land in the
  manifest's ``capabilities[]`` / ``actions[]`` arrays separately.
- Schema-version pin is mandatory in the sidecar; resolved against the
  kit's bundled ``platforms/m365/index.json``. Missing version errors;
  older-than-default soft-warns; ``deprecated`` strong-warns. Per SKL-009.
- 8K hard budget on the manifest's ``instructions`` field. Compile
  fails if exceeded.
- The compiled manifest is validated against the schema for the pinned
  version before write; this surfaces composition bugs early.

Provenance: the manifest gets a ``$comment`` field; ``instructions.md``
gets a top-line ``#`` comment.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

import jsonschema

from skl.compile._transforms import rewrite_binding_tokens
from skl.compile.budget import enforce_budget
from skl.compile.ir import CompileResult, ResolvedSkill
from skl.compile.provenance import provenance_comment
from skl.schemas import load_schema

M365_PLATFORM = "m365"

# Section order in the M365 instructions text (Identity stripped per SKL-008).
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

# Sidecar fields that pass through verbatim to the compiled manifest.
_MANIFEST_PASSTHROUGH_FIELDS: tuple[str, ...] = (
    "conversation_starters",
    "behavior_overrides",
    "disclaimer",
    "editorial_answers",
    "worker_agents",
    "user_overrides",
)


class M365SchemaError(ValueError):
    """The sidecar's ``schema_version`` cannot be resolved (missing or unknown)."""


def compile_m365(
    ir: ResolvedSkill,
    *,
    now: date | None = None,
) -> CompileResult:
    """Compile ``ir`` for M365 declarative agents.

    Raises :class:`M365SchemaError` for an unresolvable schema_version
    and :class:`skl.compile.budget.BudgetExceededError` for an
    over-budget instructions text. Compiled manifests are validated
    against the bundled schema for the pinned version before write.
    """
    sidecar = ir.sidecars.get(M365_PLATFORM)
    if sidecar is None:
        raise M365SchemaError(
            f"{ir.name}: an `skl/platforms/m365.yaml` sidecar is required "
            "for M365 compile (it carries the mandatory `schema_version` pin "
            "per SKL-009)"
        )
    sidecar_data: dict[str, Any] = sidecar.data

    schema_version = sidecar_data.get("schema_version")
    if not isinstance(schema_version, str):
        raise M365SchemaError(
            f"{ir.name}: the M365 sidecar must declare a string `schema_version` "
            "(per SKL-009); got nothing or a non-string value"
        )

    index = _load_m365_index(ir.repo_root)
    schema, warnings = _resolve_schema(ir.repo_root, schema_version, index, skill_name=ir.name)

    instructions = compose_m365_instructions(ir, sidecar_data=sidecar_data)
    enforce_budget(instructions, platform_id=M365_PLATFORM, skill_name=ir.name)

    output_root = ir.repo_root / "platforms" / "m365"
    output_root.mkdir(parents=True, exist_ok=True)

    prov = provenance_comment(ir.source_relpath, now=now)
    manifest_obj = compose_m365_manifest(
        ir,
        sidecar_data=sidecar_data,
        instructions=instructions,
        schema_version=schema_version,
        provenance=prov,
    )

    validator = jsonschema.Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(manifest_obj), key=lambda e: list(e.absolute_path))
    if errors:
        details = "; ".join(
            f"{'.'.join(str(p) for p in e.absolute_path) or '(root)'}: {e.message}" for e in errors
        )
        raise ValueError(
            f"{ir.name}: compiled M365 manifest does not validate against "
            f"declarative-agent-manifest-{schema_version}.json: {details}"
        )

    manifest_path = output_root / "declarative-agent.json"
    manifest_path.write_text(json.dumps(manifest_obj, indent=2) + "\n")

    instructions_path = output_root / "instructions.md"
    instructions_path.write_text(f"{prov}\n\n{instructions}")

    return CompileResult(
        skill_name=ir.name,
        platform_id=M365_PLATFORM,
        output_root=output_root,
        files_written=[manifest_path, instructions_path],
        warnings=warnings,
    )


# ---------------------------------------------------------------------------
# Instructions composition
# ---------------------------------------------------------------------------


def compose_m365_instructions(
    ir: ResolvedSkill,
    *,
    sidecar_data: dict[str, Any] | None = None,
) -> str:
    """Build the M365 instructions text (no provenance comment).

    Exposed so ``skl budget`` can measure the would-be instructions length
    without writing to disk. Identity stripped per SKL-008.
    """
    if sidecar_data is None:
        sidecar = ir.sidecars.get(M365_PLATFORM)
        sidecar_data = sidecar.data if sidecar is not None else {}

    bindings = sidecar_data.get("bindings") or {}
    knowledge_bindings = bindings.get("knowledge") or {}
    tool_bindings = bindings.get("tools") or {}

    parts: list[str] = []
    for section_name in _SECTION_ORDER:
        body = ir.skill.section(section_name)
        if body is None:
            continue
        body = body.strip()
        if not body:
            continue
        body = rewrite_binding_tokens(body, "knowledge", knowledge_bindings)
        body = rewrite_binding_tokens(body, "tools", tool_bindings)
        parts.append(f"## {section_name}\n\n{body}")

    return "\n\n".join(parts) + "\n"


# ---------------------------------------------------------------------------
# Manifest composition
# ---------------------------------------------------------------------------


def compose_m365_manifest(
    ir: ResolvedSkill,
    *,
    sidecar_data: dict[str, Any],
    instructions: str,
    schema_version: str,
    provenance: str | None = None,
) -> dict[str, Any]:
    """Build the M365 declarative-agent manifest dict ready for JSON dump."""
    manifest: dict[str, Any] = {
        "version": f"v{schema_version}",
        "name": ir.name,
        "description": ir.skill.description or "",
        "instructions": instructions,
    }
    if provenance is not None:
        manifest["$comment"] = provenance.lstrip("# ").strip()

    capabilities = _compose_capabilities(sidecar_data)
    if capabilities:
        manifest["capabilities"] = capabilities

    actions = _compose_actions(sidecar_data)
    if actions:
        manifest["actions"] = actions

    for key in _MANIFEST_PASSTHROUGH_FIELDS:
        value = sidecar_data.get(key)
        if value:
            manifest[key] = value

    # conversation_starters are authored as strings (sidecar convention) but
    # the M365 output schema expects objects with a `title` field. Transform.
    starters = manifest.get("conversation_starters")
    if isinstance(starters, list):
        manifest["conversation_starters"] = [
            {"title": item} if isinstance(item, str) else item for item in starters
        ]

    return manifest


def _compose_capabilities(sidecar_data: dict[str, Any]) -> list[dict[str, Any]]:
    """Build the manifest's ``capabilities[]`` from `bindings.knowledge` entries."""
    bindings = sidecar_data.get("bindings") or {}
    knowledge = bindings.get("knowledge") if isinstance(bindings, dict) else None
    if not isinstance(knowledge, dict):
        return []
    capabilities: list[dict[str, Any]] = []
    for binding_id in sorted(knowledge):
        binding = knowledge[binding_id]
        if not isinstance(binding, dict):
            continue
        if "capability" not in binding:
            continue
        entry: dict[str, Any] = {"capability": binding["capability"]}
        for key in (
            "items_by_url",
            "items_by_name",
            "items_by_id",
            "items_by_share_id",
        ):
            if key in binding:
                entry[key] = binding[key]
        capabilities.append(entry)
    return capabilities


def _compose_actions(sidecar_data: dict[str, Any]) -> list[dict[str, Any]]:
    """Build the manifest's ``actions[]`` from `bindings.tools` entries.

    Sidecar's ``actions:`` array (if any) appends after binding-derived
    entries; bindings are sorted by skill tool ID for determinism.
    """
    bindings = sidecar_data.get("bindings") or {}
    tools = bindings.get("tools") if isinstance(bindings, dict) else None
    actions: list[dict[str, Any]] = []
    if isinstance(tools, dict):
        for binding_id in sorted(tools):
            binding = tools[binding_id]
            if isinstance(binding, dict):
                actions.append(dict(binding))
    explicit = sidecar_data.get("actions") or []
    if isinstance(explicit, list):
        for item in explicit:
            if isinstance(item, dict):
                actions.append(item)
    return actions


# ---------------------------------------------------------------------------
# Schema-version resolution (SKL-009)
# ---------------------------------------------------------------------------


def _load_m365_index(repo_root: Path) -> dict[str, Any]:
    """Prefer the synced kit's ``index.json``; fall back to the bundled copy."""
    kit_path = repo_root / "_shared" / "schemas" / "platforms" / "m365" / "index.json"
    if kit_path.is_file():
        return json.loads(kit_path.read_text())
    return load_schema("platforms/m365/index.json")


def _load_m365_output_schema(repo_root: Path, version: str) -> dict[str, Any]:
    """Prefer the synced kit's bundled schema; fall back to the package copy."""
    rel = f"platforms/m365/declarative-agent-manifest-{version}.json"
    kit_path = repo_root / "_shared" / "schemas" / rel
    if kit_path.is_file():
        return json.loads(kit_path.read_text())
    return load_schema(rel)


def _resolve_schema(
    repo_root: Path,
    version: str,
    index: dict[str, Any],
    *,
    skill_name: str,
) -> tuple[dict[str, Any], list[str]]:
    """Resolve the schema for ``version`` against the kit's index per SKL-009.

    Returns the schema dict plus a list of warning strings (e.g. older
    than default, deprecated). Raises :class:`M365SchemaError` when the
    version is not in the index's ``supported`` list.
    """
    supported = index.get("supported") or []
    default = index.get("default")
    deprecated = index.get("deprecated") or []

    if version not in supported:
        raise M365SchemaError(
            f"{skill_name}: M365 schema_version {version!r} not in the kit's "
            f"`supported` list ({', '.join(supported)}). Run `skl shared sync` "
            "or pin to a supported version (per SKL-009)."
        )

    try:
        schema = _load_m365_output_schema(repo_root, version)
    except FileNotFoundError as exc:
        raise M365SchemaError(
            f"{skill_name}: declarative-agent-manifest-{version}.json missing "
            f"from both the synced kit and the bundled fallback ({exc})"
        ) from exc

    warnings: list[str] = []

    for entry in deprecated:
        if isinstance(entry, dict) and entry.get("version") == version:
            note = entry.get("note") or "deprecated"
            warnings.append(f"M365 schema version {version!r} is deprecated: {note}")
            break

    if isinstance(default, str) and version != default and version < default:
        warnings.append(
            f"M365 schema version {version!r} is older than the kit default "
            f"{default!r}; consider updating the sidecar pin"
        )

    return schema, warnings
