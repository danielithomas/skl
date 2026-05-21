"""Read and write YAML files with round-trip comment preservation.

The historical use case is ``skill-repo.yaml``, but this module is the
single point of YAML access for the whole package (per CLAUDE.md). New
features (SKILL.md frontmatter, per-platform sidecars, values files,
shared-kit config) all load through here so comment preservation and
parser behaviour are consistent.

Schema references: ``docs/spec/manifest.md`` (skill-repo),
``docs/spec/skill-md.md`` (SKILL.md frontmatter).
"""

from __future__ import annotations

from io import StringIO
from pathlib import Path
from typing import Any

from ruamel.yaml import YAML

_yaml = YAML(typ="rt")
_yaml.preserve_quotes = True
_yaml.indent(mapping=2, sequence=4, offset=2)


def load(path: Path) -> Any:
    """Load a YAML file as a ruamel CommentedMap, preserving comments."""
    with path.open() as f:
        return _yaml.load(f)


def loads(text: str) -> Any:
    """Load YAML from a string. Used for SKILL.md frontmatter and tests."""
    return _yaml.load(StringIO(text))


def save(data: Any, path: Path) -> None:
    """Save a YAML object back to disk, preserving comments and formatting."""
    with path.open("w") as f:
        _yaml.dump(data, f)


def to_plain(obj: Any) -> Any:
    """Convert ruamel CommentedMap / CommentedSeq trees to plain dict / list.

    Ruamel's mapping and sequence types subclass ``dict`` and ``list``, so a
    straight ``isinstance`` walk suffices. Conversion keeps downstream code
    (JSON Schema validation, dataclass construction) dialect-agnostic.
    """
    if isinstance(obj, dict):
        return {str(k): to_plain(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [to_plain(v) for v in obj]
    return obj


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
