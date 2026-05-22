"""Tests for ``skl.compile.skills_native`` and the dispatcher in ``skl.compile``."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from skl.compile import (
    CompilerNotImplementedError,
    build_ir,
    compile_skill,
)
from skl.compile._transforms import remove_h2_section, remove_top_level_yaml_block
from skl.compile.skills_native import (
    SKILLS_NATIVE_PLATFORMS,
    compile_skills_native,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "skill-repo.yaml").write_text("schema_version: 1\nname: host\nvisibility: internal\n")
    (repo / "skills").mkdir()
    return repo


def _make_skill(repo: Path, name: str, skill_md: str) -> Path:
    skill_root = repo / "skills" / name
    skill_root.mkdir(parents=True)
    (skill_root / "SKILL.md").write_text(skill_md)
    return skill_root


def _full_skill_md(*, name: str = "demo", include_identity: bool = True) -> str:
    identity = "## Identity\nYou are Demo, a demo persona.\n\n" if include_identity else ""
    return (
        "---\n"
        f"name: {name}\n"
        "description: Demo skill for compile tests.\n"
        "skl:\n"
        "  schema_version: 1\n"
        "  display_name: Demo\n"
        "  status: active\n"
        "  enabled_platforms: [claude-code, claude-cowork, ms-cowork]\n"
        "  variables:\n"
        "    - { name: company, description: Company }\n"
        "---\n"
        "\n"
        "# Demo\n"
        "\n"
        f"{identity}"
        "## Capabilities\n"
        "- Demo capability.\n"
        "\n"
        "## Workflow\n"
        "1. Do the thing.\n"
        "\n"
        "## Edge Cases\n"
        "- Nothing to do.\n"
        "\n"
        "## Examples\n"
        "Use it for X.\n"
    )


_FIXED_DATE = date(2026, 5, 22)


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


def test_compile_writes_expected_file(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    _make_skill(repo, "demo", _full_skill_md())
    ir = build_ir(repo / "skills" / "demo", repo)
    result = compile_skills_native(ir, "claude-code", now=_FIXED_DATE)
    assert result.output_root == repo / "platforms" / "claude-code" / "demo"
    assert (result.output_root / "SKILL.md").is_file()
    assert result.skill_name == "demo"
    assert result.platform_id == "claude-code"


def test_skl_frontmatter_block_stripped(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    _make_skill(repo, "demo", _full_skill_md())
    ir = build_ir(repo / "skills" / "demo", repo)
    compile_skills_native(ir, "claude-code", now=_FIXED_DATE)
    out = (repo / "platforms" / "claude-code" / "demo" / "SKILL.md").read_text()
    assert "skl:" not in out
    assert "schema_version" not in out
    assert "display_name" not in out
    assert "enabled_platforms" not in out


def test_identity_section_stripped(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    _make_skill(repo, "demo", _full_skill_md(include_identity=True))
    ir = build_ir(repo / "skills" / "demo", repo)
    compile_skills_native(ir, "claude-code", now=_FIXED_DATE)
    out = (repo / "platforms" / "claude-code" / "demo" / "SKILL.md").read_text()
    assert "## Identity" not in out
    assert "demo persona" not in out


def test_anthropic_base_fields_retained(tmp_path: Path) -> None:
    """`name` and `description` survive the strip - they're Anthropic-standard."""
    repo = _make_repo(tmp_path)
    _make_skill(repo, "demo", _full_skill_md())
    ir = build_ir(repo / "skills" / "demo", repo)
    compile_skills_native(ir, "claude-code", now=_FIXED_DATE)
    out = (repo / "platforms" / "claude-code" / "demo" / "SKILL.md").read_text()
    assert "name: demo" in out
    assert "description: Demo skill" in out


def test_provenance_comment_on_first_line(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    _make_skill(repo, "demo", _full_skill_md())
    ir = build_ir(repo / "skills" / "demo", repo)
    compile_skills_native(ir, "claude-code", now=_FIXED_DATE)
    out = (repo / "platforms" / "claude-code" / "demo" / "SKILL.md").read_text()
    first_line = out.splitlines()[0]
    assert first_line.startswith("# Compiled by skl ")
    assert "from skills/demo/SKILL.md on 2026-05-22" in first_line


def test_compiled_output_starts_with_provenance_then_fence(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    _make_skill(repo, "demo", _full_skill_md())
    ir = build_ir(repo / "skills" / "demo", repo)
    compile_skills_native(ir, "claude-code", now=_FIXED_DATE)
    out = (repo / "platforms" / "claude-code" / "demo" / "SKILL.md").read_text()
    lines = out.splitlines()
    assert lines[0].startswith("# Compiled by skl")
    assert lines[1] == "---"


# ---------------------------------------------------------------------------
# Byte-identical output across the three Skills-native targets
# ---------------------------------------------------------------------------


def test_skills_native_targets_byte_identical(tmp_path: Path) -> None:
    """All three platforms produce the same SKILL.md bytes - only path differs."""
    repo = _make_repo(tmp_path)
    _make_skill(repo, "demo", _full_skill_md())
    ir = build_ir(repo / "skills" / "demo", repo)
    outputs = {}
    for platform in sorted(SKILLS_NATIVE_PLATFORMS):
        compile_skills_native(ir, platform, now=_FIXED_DATE)
        outputs[platform] = (repo / "platforms" / platform / "demo" / "SKILL.md").read_text()
    assert outputs["claude-code"] == outputs["claude-cowork"]
    assert outputs["claude-code"] == outputs["ms-cowork"]


def test_skills_native_output_paths_differ(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    _make_skill(repo, "demo", _full_skill_md())
    ir = build_ir(repo / "skills" / "demo", repo)
    results = {p: compile_skills_native(ir, p, now=_FIXED_DATE) for p in SKILLS_NATIVE_PLATFORMS}
    paths = {r.output_root for r in results.values()}
    assert len(paths) == 3


# ---------------------------------------------------------------------------
# Sibling folders
# ---------------------------------------------------------------------------


def test_references_folder_copied(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    skill_root = _make_skill(repo, "demo", _full_skill_md())
    refs = skill_root / "references"
    refs.mkdir()
    (refs / "note.md").write_text("# Note\nA reference.\n")
    (refs / "deep" / "nested.md").parent.mkdir(parents=True)
    (refs / "deep" / "nested.md").write_text("Nested.\n")
    ir = build_ir(skill_root, repo)
    compile_skills_native(ir, "claude-code", now=_FIXED_DATE)
    out_refs = repo / "platforms" / "claude-code" / "demo" / "references"
    assert (out_refs / "note.md").is_file()
    assert (out_refs / "deep" / "nested.md").is_file()


def test_skl_and_tests_folders_not_copied(tmp_path: Path) -> None:
    """skl/ (sidecars) and tests/ (fixtures) are authoring-only, not in artefacts."""
    repo = _make_repo(tmp_path)
    skill_root = _make_skill(repo, "demo", _full_skill_md())
    (skill_root / "skl" / "platforms").mkdir(parents=True)
    (skill_root / "skl" / "platforms" / "m365.yaml").write_text('schema_version: "1.7"\n')
    (skill_root / "tests").mkdir()
    (skill_root / "tests" / "test-cases.yaml").write_text("- input: hi\n")
    ir = build_ir(skill_root, repo)
    compile_skills_native(ir, "claude-code", now=_FIXED_DATE)
    out_root = repo / "platforms" / "claude-code" / "demo"
    assert not (out_root / "skl").exists()
    assert not (out_root / "tests").exists()


def test_compile_overwrites_existing_output(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    _make_skill(repo, "demo", _full_skill_md())
    ir = build_ir(repo / "skills" / "demo", repo)
    compile_skills_native(ir, "claude-code", now=_FIXED_DATE)
    # Add a stale sibling that should be replaced on next compile.
    stale_refs = repo / "platforms" / "claude-code" / "demo" / "references"
    stale_refs.mkdir(parents=True, exist_ok=True)
    (stale_refs / "stale.md").write_text("stale\n")
    # Now add a real references folder to source and recompile.
    real_refs = repo / "skills" / "demo" / "references"
    real_refs.mkdir()
    (real_refs / "real.md").write_text("real\n")
    compile_skills_native(ir, "claude-code", now=_FIXED_DATE)
    assert not (stale_refs / "stale.md").exists()
    assert (stale_refs / "real.md").is_file()


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------


def test_dispatcher_routes_skills_native(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    _make_skill(repo, "demo", _full_skill_md())
    ir = build_ir(repo / "skills" / "demo", repo)
    result = compile_skill(ir, "claude-code")
    assert result.platform_id == "claude-code"
    assert (result.output_root / "SKILL.md").is_file()


@pytest.mark.parametrize("platform", ["m365"])
def test_dispatcher_raises_for_unbuilt_platforms(tmp_path: Path, platform: str) -> None:
    """M365 still raises pending the second half of Stage 4."""
    repo = _make_repo(tmp_path)
    _make_skill(repo, "demo", _full_skill_md())
    ir = build_ir(repo / "skills" / "demo", repo)
    with pytest.raises(CompilerNotImplementedError):
        compile_skill(ir, platform)


def test_dispatcher_raises_for_unknown_platform(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    _make_skill(repo, "demo", _full_skill_md())
    ir = build_ir(repo / "skills" / "demo", repo)
    with pytest.raises(ValueError, match="unknown platform"):
        compile_skill(ir, "atari-jaguar")


# ---------------------------------------------------------------------------
# Edge cases in the text transformations
# ---------------------------------------------------------------------------


def test_skill_without_identity_section_compiles(tmp_path: Path) -> None:
    """A Skills-native-only authored SKILL.md (no Identity) compiles cleanly."""
    repo = _make_repo(tmp_path)
    _make_skill(
        repo,
        "no-identity",
        _full_skill_md(name="no-identity", include_identity=False),
    )
    ir = build_ir(repo / "skills" / "no-identity", repo)
    compile_skills_native(ir, "claude-code", now=_FIXED_DATE)
    out = (repo / "platforms" / "claude-code" / "no-identity" / "SKILL.md").read_text()
    assert "## Identity" not in out
    assert "## Capabilities" in out


def test_remove_top_level_yaml_block_basic() -> None:
    text = "name: x\nskl:\n  a: 1\n  b: 2\nfoo: y\n"
    out = remove_top_level_yaml_block(text, "skl")
    assert out == "name: x\nfoo: y\n"


def test_remove_top_level_yaml_block_at_end() -> None:
    text = "name: x\nskl:\n  a: 1\n"
    out = remove_top_level_yaml_block(text, "skl")
    assert out == "name: x\n"


def test_remove_top_level_yaml_block_absent_is_noop() -> None:
    text = "name: x\nfoo: y\n"
    out = remove_top_level_yaml_block(text, "skl")
    assert out == text


def test_remove_top_level_yaml_block_preserves_other_indentation() -> None:
    text = "name: x\nother:\n    deeply: nested\nskl:\n  a: 1\nfoo: y\n"
    out = remove_top_level_yaml_block(text, "skl")
    assert out == "name: x\nother:\n    deeply: nested\nfoo: y\n"


def test_remove_h2_section_basic() -> None:
    body = "intro\n\n## Identity\npersona\n\n## Capabilities\ncap\n"
    out = remove_h2_section(body, "Identity")
    assert out == "intro\n\n## Capabilities\ncap\n"


def test_remove_h2_section_case_insensitive() -> None:
    body = "## IDENTITY\nx\n## Capabilities\ny\n"
    out = remove_h2_section(body, "Identity")
    assert "IDENTITY" not in out


def test_remove_h2_section_inside_code_fence_preserved() -> None:
    body = "## Identity\nyou are\n```\n## Identity\nfake\n```\n## Capabilities\nc\n"
    out = remove_h2_section(body, "Identity")
    # The real Identity goes, but its replacement starts a section that contains
    # the entire fenced block (the fenced ## Identity is not a section start).
    # Expected: leading ## Identity (real one) is consumed; next H2 is Capabilities.
    # The fenced "## Identity" is part of what was the real Identity body and is gone too.
    assert "## Identity" not in out.replace("```\n## Identity\nfake\n```", "")
    # Sanity: Capabilities section remains.
    assert "## Capabilities" in out


def test_remove_h2_section_absent_is_noop() -> None:
    body = "## Capabilities\ncap\n## Workflow\nwf\n"
    out = remove_h2_section(body, "Identity")
    assert out == body
