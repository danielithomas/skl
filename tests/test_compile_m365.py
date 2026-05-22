"""Tests for ``skl.compile.m365``."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from textwrap import dedent

import pytest

from skl.compile import build_ir, compile_skill
from skl.compile.budget import BudgetExceededError
from skl.compile.m365 import (
    M365SchemaError,
    compile_m365,
    compose_m365_instructions,
    compose_m365_manifest,
)

_FIXED_DATE = date(2026, 5, 22)


def _make_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "skill-repo.yaml").write_text("schema_version: 1\nname: host\nvisibility: internal\n")
    return repo


def _full_skill_md(
    *,
    name: str = "demo",
    with_identity: bool = True,
    body_extra: str = "",
) -> str:
    identity = "## Identity\nYou are Demo, a demo persona.\n\n" if with_identity else ""
    return (
        "---\n"
        f"name: {name}\n"
        "description: Demo skill for M365 tests.\n"
        "skl:\n"
        "  schema_version: 1\n"
        "  display_name: Demo\n"
        "  status: active\n"
        "  enabled_platforms: [m365]\n"
        "---\n"
        "\n"
        "# Demo\n"
        "\n"
        f"{identity}"
        "## Capabilities\n"
        "- Demo capability.\n"
        "\n"
        "## Workflow\n"
        "1. Do.\n"
        "\n"
        "## Edge Cases\n"
        "- None.\n"
        "\n"
        "## Examples\n"
        "Example.\n"
        f"{body_extra}"
    )


def _make_skill(repo: Path, name: str, content: str, *, sidecar: str) -> Path:
    skill_root = repo / "skills" / name
    skill_root.mkdir(parents=True)
    (skill_root / "SKILL.md").write_text(content)
    platforms_dir = skill_root / "skl" / "platforms"
    platforms_dir.mkdir(parents=True)
    (platforms_dir / "m365.yaml").write_text(dedent(sidecar))
    return skill_root


# ---------------------------------------------------------------------------
# Output structure
# ---------------------------------------------------------------------------


def test_compile_writes_manifest_and_instructions(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    _make_skill(repo, "demo", _full_skill_md(), sidecar='schema_version: "1.7"\n')
    ir = build_ir(repo / "skills" / "demo", repo)
    result = compile_m365(ir, now=_FIXED_DATE)
    assert result.output_root == repo / "platforms" / "m365"
    manifest_path = repo / "platforms" / "m365" / "declarative-agent.json"
    instructions_path = repo / "platforms" / "m365" / "instructions.md"
    assert manifest_path.is_file()
    assert instructions_path.is_file()
    assert manifest_path in result.files_written
    assert instructions_path in result.files_written


def test_manifest_version_matches_schema_pin(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    _make_skill(repo, "demo", _full_skill_md(), sidecar='schema_version: "1.7"\n')
    ir = build_ir(repo / "skills" / "demo", repo)
    compile_m365(ir, now=_FIXED_DATE)
    manifest = json.loads((repo / "platforms" / "m365" / "declarative-agent.json").read_text())
    assert manifest["version"] == "v1.7"


def test_manifest_has_provenance_comment(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    _make_skill(repo, "demo", _full_skill_md(), sidecar='schema_version: "1.7"\n')
    ir = build_ir(repo / "skills" / "demo", repo)
    compile_m365(ir, now=_FIXED_DATE)
    manifest = json.loads((repo / "platforms" / "m365" / "declarative-agent.json").read_text())
    assert "$comment" in manifest
    assert "Compiled by skl" in manifest["$comment"]
    assert "2026-05-22" in manifest["$comment"]


def test_instructions_md_has_provenance_line(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    _make_skill(repo, "demo", _full_skill_md(), sidecar='schema_version: "1.7"\n')
    ir = build_ir(repo / "skills" / "demo", repo)
    compile_m365(ir, now=_FIXED_DATE)
    text = (repo / "platforms" / "m365" / "instructions.md").read_text()
    assert text.splitlines()[0].startswith("# Compiled by skl ")


def test_manifest_carries_name_description_instructions(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    _make_skill(repo, "demo", _full_skill_md(), sidecar='schema_version: "1.7"\n')
    ir = build_ir(repo / "skills" / "demo", repo)
    compile_m365(ir, now=_FIXED_DATE)
    manifest = json.loads((repo / "platforms" / "m365" / "declarative-agent.json").read_text())
    assert manifest["name"] == "demo"
    assert manifest["description"] == "Demo skill for M365 tests."
    assert "## Capabilities" in manifest["instructions"]
    # Manifest's instructions matches the body of instructions.md (minus prov).
    md_text = (repo / "platforms" / "m365" / "instructions.md").read_text()
    body = md_text.split("\n\n", maxsplit=1)[1]
    assert manifest["instructions"] == body


# ---------------------------------------------------------------------------
# Identity is stripped (SKL-008)
# ---------------------------------------------------------------------------


def test_identity_section_stripped(tmp_path: Path) -> None:
    """SKL-008: M365 strips Identity by default."""
    repo = _make_repo(tmp_path)
    _make_skill(
        repo,
        "demo",
        _full_skill_md(with_identity=True),
        sidecar='schema_version: "1.7"\n',
    )
    ir = build_ir(repo / "skills" / "demo", repo)
    compile_m365(ir, now=_FIXED_DATE)
    manifest = json.loads((repo / "platforms" / "m365" / "declarative-agent.json").read_text())
    assert "## Identity" not in manifest["instructions"]
    assert "demo persona" not in manifest["instructions"]


# ---------------------------------------------------------------------------
# Bindings -> capabilities / actions
# ---------------------------------------------------------------------------


def test_bindings_knowledge_render_as_capabilities(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    _make_skill(
        repo,
        "demo",
        _full_skill_md(),
        sidecar=dedent(
            """\
            schema_version: "1.7"
            bindings:
              knowledge:
                case-study-library:
                  capability: OneDriveAndSharePoint
                  items_by_url: ["https://contoso.sharepoint.com/sites/cases"]
            """
        ),
    )
    ir = build_ir(repo / "skills" / "demo", repo)
    compile_m365(ir, now=_FIXED_DATE)
    manifest = json.loads((repo / "platforms" / "m365" / "declarative-agent.json").read_text())
    assert manifest["capabilities"] == [
        {
            "capability": "OneDriveAndSharePoint",
            "items_by_url": ["https://contoso.sharepoint.com/sites/cases"],
        }
    ]


def test_bindings_tools_render_as_actions(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    _make_skill(
        repo,
        "demo",
        _full_skill_md(),
        sidecar=dedent(
            """\
            schema_version: "1.7"
            bindings:
              tools:
                web_fetch:
                  action: web-fetch-plugin
            """
        ),
    )
    ir = build_ir(repo / "skills" / "demo", repo)
    compile_m365(ir, now=_FIXED_DATE)
    manifest = json.loads((repo / "platforms" / "m365" / "declarative-agent.json").read_text())
    assert manifest["actions"] == [{"action": "web-fetch-plugin"}]


def test_passthrough_fields_land_in_manifest(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    _make_skill(
        repo,
        "demo",
        _full_skill_md(),
        sidecar=dedent(
            """\
            schema_version: "1.7"
            conversation_starters:
              - "Find case studies"
              - "Show me bids"
            behavior_overrides:
              default_response_mode: Auto
            disclaimer:
              text: Verify before use.
            """
        ),
    )
    ir = build_ir(repo / "skills" / "demo", repo)
    compile_m365(ir, now=_FIXED_DATE)
    manifest = json.loads((repo / "platforms" / "m365" / "declarative-agent.json").read_text())
    # Sidecar accepts strings; manifest stores objects (M365 schema requirement).
    assert manifest["conversation_starters"] == [
        {"title": "Find case studies"},
        {"title": "Show me bids"},
    ]
    assert manifest["behavior_overrides"] == {"default_response_mode": "Auto"}
    assert manifest["disclaimer"] == {"text": "Verify before use."}


# ---------------------------------------------------------------------------
# Schema version resolution (SKL-009)
# ---------------------------------------------------------------------------


def test_missing_sidecar_errors(tmp_path: Path) -> None:
    """M365 requires a sidecar with the schema_version pin."""
    repo = _make_repo(tmp_path)
    skill_root = repo / "skills" / "demo"
    skill_root.mkdir(parents=True)
    (skill_root / "SKILL.md").write_text(_full_skill_md())
    ir = build_ir(skill_root, repo)
    with pytest.raises(M365SchemaError, match="sidecar is required"):
        compile_m365(ir, now=_FIXED_DATE)


def test_missing_schema_version_errors(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    _make_skill(repo, "demo", _full_skill_md(), sidecar="bindings: {}\n")
    ir = build_ir(repo / "skills" / "demo", repo)
    with pytest.raises(M365SchemaError, match="schema_version"):
        compile_m365(ir, now=_FIXED_DATE)


def test_unknown_schema_version_errors(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    _make_skill(repo, "demo", _full_skill_md(), sidecar='schema_version: "9.9"\n')
    ir = build_ir(repo / "skills" / "demo", repo)
    with pytest.raises(M365SchemaError, match="not in the kit's `supported`"):
        compile_m365(ir, now=_FIXED_DATE)


def test_deprecated_version_warns(tmp_path: Path) -> None:
    """Per SKL-009, deprecated versions surface a strong warning on the result."""
    repo = _make_repo(tmp_path)
    # Override the kit's index.json with a custom one that marks 1.7 as deprecated.
    kit_dir = repo / "_shared" / "schemas" / "platforms" / "m365"
    kit_dir.mkdir(parents=True)
    (kit_dir / "index.json").write_text(
        json.dumps(
            {
                "default": "1.7",
                "supported": ["1.7"],
                "deprecated": [{"version": "1.7", "note": "Microsoft retires 1.7 after 2026-09"}],
            }
        )
    )
    _make_skill(repo, "demo", _full_skill_md(), sidecar='schema_version: "1.7"\n')
    ir = build_ir(repo / "skills" / "demo", repo)
    result = compile_m365(ir, now=_FIXED_DATE)
    assert any("deprecated" in w for w in result.warnings)


def test_kit_index_overrides_bundled(tmp_path: Path) -> None:
    """When `_shared/schemas/platforms/m365/index.json` exists, it shadows the bundled."""
    repo = _make_repo(tmp_path)
    # Custom kit index that only supports a fictional 9.9 (so 1.7 is unsupported).
    kit_dir = repo / "_shared" / "schemas" / "platforms" / "m365"
    kit_dir.mkdir(parents=True)
    (kit_dir / "index.json").write_text(
        json.dumps({"default": "9.9", "supported": ["9.9"], "deprecated": []})
    )
    _make_skill(repo, "demo", _full_skill_md(), sidecar='schema_version: "1.7"\n')
    ir = build_ir(repo / "skills" / "demo", repo)
    with pytest.raises(M365SchemaError, match="not in the kit's `supported`"):
        compile_m365(ir, now=_FIXED_DATE)


# ---------------------------------------------------------------------------
# Manifest validates against schema
# ---------------------------------------------------------------------------


def test_compiled_manifest_validates_against_schema(tmp_path: Path) -> None:
    """Sanity check: write + reload + validate against the bundled schema."""
    import jsonschema

    from skl.schemas import load_schema

    repo = _make_repo(tmp_path)
    _make_skill(
        repo,
        "demo",
        _full_skill_md(),
        sidecar=dedent(
            """\
            schema_version: "1.7"
            bindings:
              knowledge:
                kb:
                  capability: OneDriveAndSharePoint
                  items_by_url: ["https://x"]
              tools:
                web_fetch:
                  action: web-fetch-plugin
            conversation_starters:
              - "Find x"
            disclaimer:
              text: "AI-generated; verify."
            """
        ),
    )
    ir = build_ir(repo / "skills" / "demo", repo)
    compile_m365(ir, now=_FIXED_DATE)
    manifest = json.loads((repo / "platforms" / "m365" / "declarative-agent.json").read_text())
    schema = load_schema("platforms/m365/declarative-agent-manifest-1.7.json")
    jsonschema.Draft202012Validator(schema).validate(manifest)


# ---------------------------------------------------------------------------
# 8K budget on instructions
# ---------------------------------------------------------------------------


def test_8k_budget_enforced_on_instructions(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    huge = "x " * 5000  # ~10K chars in the body
    _make_skill(
        repo,
        "huge",
        _full_skill_md(body_extra=f"\n\n{huge}\n"),
        sidecar='schema_version: "1.7"\n',
    )
    ir = build_ir(repo / "skills" / "huge", repo)
    with pytest.raises(BudgetExceededError, match="m365"):
        compile_m365(ir, now=_FIXED_DATE)


# ---------------------------------------------------------------------------
# Dispatcher + CLI
# ---------------------------------------------------------------------------


def test_dispatcher_routes_m365(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    _make_skill(repo, "demo", _full_skill_md(), sidecar='schema_version: "1.7"\n')
    ir = build_ir(repo / "skills" / "demo", repo)
    result = compile_skill(ir, "m365")
    assert result.platform_id == "m365"


def test_cli_compile_m365(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from click.testing import CliRunner

    from skl import __version__
    from skl.cli import main

    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "skill-repo.yaml").write_text(
        f"""\
schema_version: 1
name: host
visibility: internal
skl_version: ">={__version__},<99.0"
shared_kit:
  source: github.com/example/kit
  version: "1.0.0"
enabled_platforms: []
"""
    )
    _make_skill(repo, "demo", _full_skill_md(), sidecar='schema_version: "1.7"\n')
    monkeypatch.chdir(repo)
    runner = CliRunner()
    result = runner.invoke(main, ["compile", "--platform", "m365"])
    assert result.exit_code == 0, result.output
    assert (repo / "platforms" / "m365" / "declarative-agent.json").is_file()


# ---------------------------------------------------------------------------
# compose_* helpers (unit-level)
# ---------------------------------------------------------------------------


def test_compose_m365_instructions_strips_identity(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    _make_skill(repo, "demo", _full_skill_md(), sidecar='schema_version: "1.7"\n')
    ir = build_ir(repo / "skills" / "demo", repo)
    text = compose_m365_instructions(ir)
    assert "## Identity" not in text
    assert "## Capabilities" in text


def test_compose_m365_manifest_minimal_shape(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    _make_skill(repo, "demo", _full_skill_md(), sidecar='schema_version: "1.7"\n')
    ir = build_ir(repo / "skills" / "demo", repo)
    manifest = compose_m365_manifest(
        ir,
        sidecar_data={"schema_version": "1.7"},
        instructions="## Capabilities\nx\n",
        schema_version="1.7",
    )
    assert manifest["version"] == "v1.7"
    assert manifest["name"] == "demo"
    assert manifest["instructions"] == "## Capabilities\nx\n"
    assert "capabilities" not in manifest  # no bindings declared
