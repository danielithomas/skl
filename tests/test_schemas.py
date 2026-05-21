"""Tests for the bundled JSON Schemas under ``skl.schemas``.

These tests confirm that every schema we ship is itself a valid JSON Schema
(it validates against the Draft 2020-12 meta-schema) and that it accepts
known-good shapes and rejects known-bad shapes for the most load-bearing
constraints. They do not aim to exhaustively cover every keyword; the
``skl validate`` test suite exercises the schemas in their real context.

Schemas covered:
- ``skill-repo.schema.json`` (already used by ``skl validate``)
- ``skill.frontmatter.schema.json`` (per SKL-004)
- ``platforms/copilot-studio.schema.json``
- ``platforms/m365.schema.json`` (sidecar input)
- ``platforms/vscode.schema.json``
- ``platforms/m365/declarative-agent-manifest-1.7.json`` (compiled output)
- ``platforms/m365/index.json`` (kit index, not a schema)
"""

from __future__ import annotations

from typing import Any

import jsonschema
import pytest

from skl.schemas import load_schema

BUNDLED_SCHEMAS = (
    "skill-repo.schema.json",
    "skill.frontmatter.schema.json",
    "platforms/copilot-studio.schema.json",
    "platforms/m365.schema.json",
    "platforms/vscode.schema.json",
    "platforms/m365/declarative-agent-manifest-1.7.json",
)


@pytest.mark.parametrize("name", BUNDLED_SCHEMAS)
def test_schema_loads(name: str) -> None:
    """Every bundled schema parses as JSON and exposes the standard top-level keys."""
    schema = load_schema(name)
    assert isinstance(schema, dict)
    assert schema.get("$schema") == "https://json-schema.org/draft/2020-12/schema"
    assert "title" in schema
    assert "type" in schema


@pytest.mark.parametrize("name", BUNDLED_SCHEMAS)
def test_schema_is_valid_against_meta_schema(name: str) -> None:
    """Each bundled schema is itself a valid Draft 2020-12 JSON Schema."""
    schema = load_schema(name)
    jsonschema.Draft202012Validator.check_schema(schema)


def _validate(schema_name: str, instance: dict[str, Any]) -> list[jsonschema.ValidationError]:
    schema = load_schema(schema_name)
    validator = jsonschema.Draft202012Validator(schema)
    return sorted(validator.iter_errors(instance), key=lambda e: list(e.absolute_path))


# ---------------------------------------------------------------------------
# SKILL.md frontmatter
# ---------------------------------------------------------------------------


def _good_frontmatter() -> dict[str, Any]:
    """Minimal frontmatter that satisfies the master schema."""
    return {
        "name": "casey-case-studies",
        "description": "Retrieve and synthesise case studies from the firm's library.",
        "skl": {
            "schema_version": 1,
            "display_name": "Casey - Case Studies",
            "status": "active",
            "enabled_platforms": ["claude-code"],
        },
    }


def test_frontmatter_accepts_minimal_valid_shape() -> None:
    assert _validate("skill.frontmatter.schema.json", _good_frontmatter()) == []


def test_frontmatter_accepts_full_worked_example() -> None:
    """The SKL-004 worked example validates cleanly."""
    instance = {
        "name": "casey-case-studies",
        "description": "Retrieve and synthesise consulting case studies.",
        "skl": {
            "schema_version": 1,
            "display_name": "Casey - Case Studies",
            "status": "active",
            "lifecycle": "business_development",
            "persona": {"nickname": "Casey", "role": "Case Studies Specialist"},
            "enabled_platforms": ["copilot-studio", "m365", "claude-code", "claude-cowork"],
            "variables": [
                {
                    "name": "consulting_company",
                    "description": "The firm running the skill",
                    "required": True,
                },
            ],
            "knowledge": [
                {"id": "case-study-library", "contract": "knowledge/case-studies.contract.md"},
            ],
            "tools": [{"id": "web_fetch"}],
        },
    }
    assert _validate("skill.frontmatter.schema.json", instance) == []


def test_frontmatter_rejects_uppercase_name() -> None:
    bad = _good_frontmatter()
    bad["name"] = "Casey-Case-Studies"
    errors = _validate("skill.frontmatter.schema.json", bad)
    assert any("pattern" in e.message.lower() or "match" in e.message.lower() for e in errors)


def test_frontmatter_rejects_overlong_description() -> None:
    bad = _good_frontmatter()
    bad["description"] = "x" * 1001
    errors = _validate("skill.frontmatter.schema.json", bad)
    assert any("too long" in e.message.lower() for e in errors)


def test_frontmatter_rejects_unknown_status() -> None:
    bad = _good_frontmatter()
    bad["skl"]["status"] = "shipping"
    errors = _validate("skill.frontmatter.schema.json", bad)
    assert errors, "expected status enum violation"


def test_frontmatter_rejects_unknown_platform() -> None:
    bad = _good_frontmatter()
    bad["skl"]["enabled_platforms"] = ["claude-code", "made-up-platform"]
    errors = _validate("skill.frontmatter.schema.json", bad)
    assert errors


def test_frontmatter_rejects_unknown_skl_key() -> None:
    """`skl:` block is strict - typos are caught."""
    bad = _good_frontmatter()
    bad["skl"]["lifecycel"] = "business_development"  # typo
    errors = _validate("skill.frontmatter.schema.json", bad)
    assert any("additional" in e.message.lower() for e in errors)


def test_frontmatter_allows_unknown_top_level_key() -> None:
    """Unknown top-level keys pass through - Anthropic might add fields."""
    instance = _good_frontmatter()
    instance["author"] = "Anthropic"
    instance["compatibility"] = {"claude": ">=4.0"}
    assert _validate("skill.frontmatter.schema.json", instance) == []


# ---------------------------------------------------------------------------
# Copilot Studio sidecar
# ---------------------------------------------------------------------------


def test_copilot_studio_accepts_minimal() -> None:
    assert _validate("platforms/copilot-studio.schema.json", {}) == []


def test_copilot_studio_accepts_worked_example() -> None:
    instance = {
        "bindings": {
            "knowledge": {"case-study-library": "Case Studies Library"},
            "tools": {"web_fetch": "Web Fetch"},
        },
        "budget": 7500,
    }
    assert _validate("platforms/copilot-studio.schema.json", instance) == []


def test_copilot_studio_rejects_budget_above_cap() -> None:
    errors = _validate("platforms/copilot-studio.schema.json", {"budget": 9000})
    assert errors


# ---------------------------------------------------------------------------
# M365 sidecar input
# ---------------------------------------------------------------------------


def test_m365_requires_schema_version() -> None:
    """SKL-009: schema_version is mandatory."""
    errors = _validate("platforms/m365.schema.json", {})
    assert any("schema_version" in e.message for e in errors)


def test_m365_accepts_worked_example() -> None:
    instance = {
        "schema_version": "1.7",
        "bindings": {
            "knowledge": {
                "case-study-library": {
                    "capability": "OneDriveAndSharePoint",
                    "items_by_url": ["{{variables.case_study_library_path}}"],
                }
            },
            "tools": {"web_fetch": {"action": "web-fetch-plugin"}},
        },
        "behavior_overrides": {"default_response_mode": "Auto"},
        "conversation_starters": [
            "Find case studies for a banking client",
            "What have we done in healthcare consulting?",
        ],
        "disclaimer": {"text": "Case studies summarised by AI; verify before use."},
    }
    assert _validate("platforms/m365.schema.json", instance) == []


def test_m365_rejects_too_many_conversation_starters() -> None:
    instance: dict[str, Any] = {
        "schema_version": "1.7",
        "conversation_starters": [f"starter {i}" for i in range(13)],
    }
    errors = _validate("platforms/m365.schema.json", instance)
    assert errors


def test_m365_rejects_unknown_capability() -> None:
    instance = {
        "schema_version": "1.7",
        "bindings": {
            "knowledge": {"x": {"capability": "ImaginaryCapability"}},
        },
    }
    errors = _validate("platforms/m365.schema.json", instance)
    assert errors


# ---------------------------------------------------------------------------
# VS Code sidecar
# ---------------------------------------------------------------------------


def test_vscode_accepts_minimal() -> None:
    assert _validate("platforms/vscode.schema.json", {}) == []


def test_vscode_accepts_emit_skill_false() -> None:
    instance = {"emit_skill": False, "target": "vscode", "model": "claude-opus-4-7"}
    assert _validate("platforms/vscode.schema.json", instance) == []


def test_vscode_model_accepts_string_or_array() -> None:
    assert _validate("platforms/vscode.schema.json", {"model": "claude-opus-4-7"}) == []
    assert _validate("platforms/vscode.schema.json", {"model": ["a", "b"]}) == []
    errors = _validate("platforms/vscode.schema.json", {"model": []})
    assert errors  # empty array rejected


def test_vscode_rejects_unknown_target() -> None:
    errors = _validate("platforms/vscode.schema.json", {"target": "atom"})
    assert errors


# ---------------------------------------------------------------------------
# M365 declarative-agent manifest v1.7 (compiled output)
# ---------------------------------------------------------------------------


def _good_m365_manifest() -> dict[str, Any]:
    return {
        "version": "v1.7",
        "name": "Casey - Case Studies",
        "description": "Retrieve and synthesise case studies.",
        "instructions": "You are Casey...",
    }


def test_m365_manifest_accepts_minimal() -> None:
    assert (
        _validate("platforms/m365/declarative-agent-manifest-1.7.json", _good_m365_manifest()) == []
    )


def test_m365_manifest_rejects_wrong_version_const() -> None:
    bad = _good_m365_manifest()
    bad["version"] = "v1.6"
    errors = _validate("platforms/m365/declarative-agent-manifest-1.7.json", bad)
    assert errors


def test_m365_manifest_rejects_overlong_instructions() -> None:
    bad = _good_m365_manifest()
    bad["instructions"] = "x" * 8001
    errors = _validate("platforms/m365/declarative-agent-manifest-1.7.json", bad)
    assert any("too long" in e.message.lower() for e in errors)


# ---------------------------------------------------------------------------
# M365 schema index
# ---------------------------------------------------------------------------


def test_m365_index_shape() -> None:
    """The bundled M365 index declares default / supported / deprecated."""
    index = load_schema("platforms/m365/index.json")
    assert index["default"] in index["supported"]
    assert isinstance(index["supported"], list)
    assert isinstance(index["deprecated"], list)
    # Every entry in `deprecated` must reference a version in `supported`.
    for entry in index["deprecated"]:
        assert entry["version"] in index["supported"]
