"""Bundled JSON Schemas consumed by ``skl validate`` and ``skl compile``.

Schemas live as JSON files inside this package and travel inside the
installed wheel. The synced shared kit (under a repo's ``_shared/schemas/``)
is intended to shadow these once ``ai-skills-shared`` is bootstrapped (per
D-011); for v0.1 the bundled copy is the only source.

Use :func:`load_schema` to load any schema by its package-relative path,
including nested paths (e.g. ``"platforms/m365/declarative-agent-manifest-1.7.json"``).
"""

from __future__ import annotations

import json
from importlib import resources
from typing import Any


def load_schema(name: str) -> dict[str, Any]:
    """Load a bundled JSON Schema by its path within this package.

    ``name`` is a forward-slash path relative to ``skl.schemas`` -
    e.g. ``"skill-repo.schema.json"`` or ``"platforms/copilot-studio.schema.json"``.
    Raises :class:`FileNotFoundError` if the schema is not in the bundle.
    """
    parts = name.split("/")
    target = resources.files("skl.schemas")
    for part in parts:
        target = target.joinpath(part)
    return json.loads(target.read_text())
