"""Tests for ``skl.sidecars`` - per-platform sidecar parsing."""

from __future__ import annotations

from pathlib import Path
from textwrap import dedent

import pytest

from skl.sidecars import Sidecar, SidecarParseError, Sidecars, parse_sidecars


def _make_skill_with_sidecars(skill_root: Path, sidecars: dict[str, str]) -> None:
    platforms = skill_root / "skl" / "platforms"
    platforms.mkdir(parents=True)
    for platform_id, content in sidecars.items():
        (platforms / f"{platform_id}.yaml").write_text(dedent(content))


def test_no_sidecar_directory_returns_empty(tmp_path: Path) -> None:
    """A skill with no `skl/platforms/` directory yields an empty Sidecars."""
    skill_root = tmp_path / "simple-skill"
    skill_root.mkdir()
    sidecars = parse_sidecars(skill_root)
    assert isinstance(sidecars, Sidecars)
    assert sidecars.by_platform == {}
    assert sidecars.platform_ids == []


def test_single_sidecar(tmp_path: Path) -> None:
    skill_root = tmp_path / "casey"
    skill_root.mkdir()
    _make_skill_with_sidecars(
        skill_root,
        {
            "copilot-studio": """\
                bindings:
                  knowledge: { case-study-library: "Case Studies Library" }
                  tools: { web_fetch: "Web Fetch" }
                budget: 7500
            """
        },
    )
    sidecars = parse_sidecars(skill_root)
    assert sidecars.platform_ids == ["copilot-studio"]
    cs = sidecars.get("copilot-studio")
    assert cs is not None
    assert isinstance(cs, Sidecar)
    assert cs.platform_id == "copilot-studio"
    assert cs.data["budget"] == 7500
    assert cs.data["bindings"]["knowledge"]["case-study-library"] == "Case Studies Library"


def test_multiple_sidecars_keyed_by_stem(tmp_path: Path) -> None:
    skill_root = tmp_path / "casey"
    skill_root.mkdir()
    _make_skill_with_sidecars(
        skill_root,
        {
            "copilot-studio": "budget: 7500\n",
            "m365": 'schema_version: "1.7"\n',
            "vscode": "emit_skill: false\n",
        },
    )
    sidecars = parse_sidecars(skill_root)
    assert sidecars.platform_ids == ["copilot-studio", "m365", "vscode"]
    assert sidecars.has("m365")
    assert not sidecars.has("claude-code")


def test_empty_yaml_yields_empty_data(tmp_path: Path) -> None:
    """A sidecar that's an empty file is treated as empty config, not an error."""
    skill_root = tmp_path / "empty"
    skill_root.mkdir()
    _make_skill_with_sidecars(skill_root, {"vscode": ""})
    sidecars = parse_sidecars(skill_root)
    assert sidecars.get("vscode").data == {}  # type: ignore[union-attr]


def test_non_mapping_sidecar_raises(tmp_path: Path) -> None:
    skill_root = tmp_path / "bad"
    skill_root.mkdir()
    _make_skill_with_sidecars(skill_root, {"vscode": "- just a list\n"})
    with pytest.raises(SidecarParseError, match="must be a YAML mapping"):
        parse_sidecars(skill_root)


def test_unparseable_sidecar_raises(tmp_path: Path) -> None:
    skill_root = tmp_path / "bad"
    skill_root.mkdir()
    _make_skill_with_sidecars(skill_root, {"m365": "schema_version: [unclosed\n"})
    with pytest.raises(SidecarParseError, match="could not be parsed"):
        parse_sidecars(skill_root)


def test_non_yaml_files_are_ignored(tmp_path: Path) -> None:
    """Only `*.yaml` files are read; readme.md / config.json / .yml are ignored."""
    skill_root = tmp_path / "mixed"
    skill_root.mkdir()
    _make_skill_with_sidecars(skill_root, {"vscode": "emit_skill: false\n"})
    platforms = skill_root / "skl" / "platforms"
    (platforms / "README.md").write_text("a note\n")
    (platforms / "config.json").write_text("{}\n")
    (platforms / "m365.yml").write_text("schema_version: '1.7'\n")  # .yml not .yaml
    sidecars = parse_sidecars(skill_root)
    assert sidecars.platform_ids == ["vscode"]
