"""Read and write ``skill-repo.yaml`` with round-trip comment preservation.

Uses ``ruamel.yaml`` so user-authored comments and formatting survive the
write cycle. This is the lowest-level access; higher-level validation will
land with ``skl validate``. Schema reference: ``docs/spec/manifest.md``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ruamel.yaml import YAML

_yaml = YAML(typ="rt")
_yaml.preserve_quotes = True
_yaml.indent(mapping=2, sequence=4, offset=2)


def load(path: Path) -> Any:
    """Load a manifest file as a ruamel CommentedMap, preserving comments."""
    with path.open() as f:
        return _yaml.load(f)


def save(data: Any, path: Path) -> None:
    """Save a manifest object back to disk, preserving comments and formatting."""
    with path.open("w") as f:
        _yaml.dump(data, f)


def set_shared_kit_fields(manifest_path: Path, **fields: Any) -> None:
    """Set one or more ``shared_kit.*`` keys, preserving the rest of the file.

    Example: ``set_shared_kit_fields(p, version="1.0.0", pinned_sha="abc1234")``.
    """
    data = load(manifest_path)
    shared_kit = data.get("shared_kit")
    if shared_kit is None:
        shared_kit = {}
        data["shared_kit"] = shared_kit
    for key, value in fields.items():
        shared_kit[key] = value
    save(data, manifest_path)
