"""Parse per-platform sidecars under a skill's ``skl/platforms/`` directory.

Sidecars are the home for per-platform bindings and overrides (per SKL-004).
This module is parsing only - schema validation happens in ``skl validate``
against the per-platform sidecar schemas under
``skl.schemas.platforms.<platform>.schema.json``.

Layout:

    casey-case-studies/
    └── skl/
        └── platforms/
            ├── copilot-studio.yaml
            ├── m365.yaml
            └── vscode.yaml

The stem of each file is the platform ID. A skill with no ``skl/platforms/``
directory has no sidecars - the parser returns an empty :class:`Sidecars`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from skl import manifest


class SidecarParseError(ValueError):
    """A sidecar YAML file could not be parsed or had the wrong top-level shape."""


@dataclass
class Sidecar:
    """A single parsed sidecar."""

    platform_id: str
    path: Path
    data: dict[str, Any]


@dataclass
class Sidecars:
    """All sidecars under a skill's ``skl/platforms/`` directory."""

    by_platform: dict[str, Sidecar] = field(default_factory=dict)

    def get(self, platform_id: str) -> Sidecar | None:
        return self.by_platform.get(platform_id)

    def has(self, platform_id: str) -> bool:
        return platform_id in self.by_platform

    @property
    def platform_ids(self) -> list[str]:
        """Platform IDs that have a sidecar, in sorted order."""
        return sorted(self.by_platform)


def parse_sidecars(skill_root: Path) -> Sidecars:
    """Read every ``*.yaml`` file under ``<skill_root>/skl/platforms/``.

    Missing directory yields an empty :class:`Sidecars`. Parse failures raise
    :class:`SidecarParseError` with the offending path attached.
    """
    platforms_dir = skill_root / "skl" / "platforms"
    if not platforms_dir.is_dir():
        return Sidecars()

    by_platform: dict[str, Sidecar] = {}
    for path in sorted(platforms_dir.glob("*.yaml")):
        platform_id = path.stem
        try:
            raw = manifest.load(path)
        except Exception as exc:
            raise SidecarParseError(
                f"sidecar at {path} could not be parsed as YAML: {exc}"
            ) from exc
        if raw is None:
            data: dict[str, Any] = {}
        elif isinstance(raw, dict):
            data = manifest.to_plain(raw)
        else:
            raise SidecarParseError(
                f"sidecar at {path} must be a YAML mapping; got {type(raw).__name__}"
            )
        by_platform[platform_id] = Sidecar(platform_id=platform_id, path=path, data=data)
    return Sidecars(by_platform=by_platform)
