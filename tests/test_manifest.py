"""Tests for the manifest read/write helpers.

Focus is on round-trip preservation of user-authored content (comments,
quoting, ordering) when ``skl`` updates a manifest in place.
"""

from __future__ import annotations

from pathlib import Path
from textwrap import dedent

from skl import manifest


def _write(path: Path, content: str) -> None:
    path.write_text(dedent(content))


def test_load_returns_mapping_with_top_level_fields(tmp_path: Path) -> None:
    manifest_path = tmp_path / "skill-repo.yaml"
    _write(
        manifest_path,
        """\
        schema_version: 1
        name: example
        shared_kit:
          source: github.com/example/kit
          version: "1.0.0"
        """,
    )
    data = manifest.load(manifest_path)
    assert data["name"] == "example"
    assert data["shared_kit"]["source"] == "github.com/example/kit"
    assert data["shared_kit"]["version"] == "1.0.0"


def test_save_preserves_top_level_comments(tmp_path: Path) -> None:
    manifest_path = tmp_path / "skill-repo.yaml"
    _write(
        manifest_path,
        """\
        # Important manifest comment.
        schema_version: 1
        name: example
        shared_kit:
          source: github.com/example/kit
          version: "1.0.0"
        """,
    )
    data = manifest.load(manifest_path)
    manifest.save(data, manifest_path)
    text = manifest_path.read_text()
    assert "# Important manifest comment." in text


def test_set_shared_kit_fields_writes_pinned_sha(tmp_path: Path) -> None:
    manifest_path = tmp_path / "skill-repo.yaml"
    _write(
        manifest_path,
        """\
        schema_version: 1
        name: example
        shared_kit:
          source: github.com/example/kit
          version: "1.0.0"
        """,
    )
    manifest.set_shared_kit_fields(manifest_path, pinned_sha="abc123def456")
    text = manifest_path.read_text()
    assert "pinned_sha: abc123def456" in text
    # Existing fields preserved.
    assert "source: github.com/example/kit" in text
    assert 'version: "1.0.0"' in text


def test_set_shared_kit_fields_can_update_multiple_keys(tmp_path: Path) -> None:
    manifest_path = tmp_path / "skill-repo.yaml"
    _write(
        manifest_path,
        """\
        schema_version: 1
        name: example
        shared_kit:
          source: github.com/example/kit
          version: "latest"
        """,
    )
    manifest.set_shared_kit_fields(manifest_path, version="2.1.0", pinned_sha="deadbeef0000")
    data = manifest.load(manifest_path)
    assert data["shared_kit"]["version"] == "2.1.0"
    assert data["shared_kit"]["pinned_sha"] == "deadbeef0000"


def test_set_shared_kit_fields_creates_block_if_missing(tmp_path: Path) -> None:
    manifest_path = tmp_path / "skill-repo.yaml"
    _write(
        manifest_path,
        """\
        schema_version: 1
        name: example
        """,
    )
    manifest.set_shared_kit_fields(manifest_path, source="github.com/x/y", version="1.0.0")
    data = manifest.load(manifest_path)
    assert data["shared_kit"]["source"] == "github.com/x/y"
    assert data["shared_kit"]["version"] == "1.0.0"


def test_save_preserves_inline_comment_on_shared_kit_field(tmp_path: Path) -> None:
    manifest_path = tmp_path / "skill-repo.yaml"
    _write(
        manifest_path,
        """\
        schema_version: 1
        name: example
        shared_kit:
          source: github.com/example/kit
          version: "1.0.0"
          # pinned_sha is auto-written by skl shared sync; do not hand-edit.
        """,
    )
    manifest.set_shared_kit_fields(manifest_path, pinned_sha="abc123def456")
    text = manifest_path.read_text()
    assert "# pinned_sha is auto-written" in text
    assert "pinned_sha: abc123def456" in text
