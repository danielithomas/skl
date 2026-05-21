"""Bundled scaffold templates for ``skl init`` (repo-scoped form).

Templates are text files with ``{{PLACEHOLDER}}`` markers (distinct from
the ``{{variables.X}}`` token form used in SKILL.md content, because they
have no dot). Substitution is via plain :func:`str.replace`.

The synced shared kit (under ``_shared/templates/``) is intended to shadow
these once ``ai-skills-shared`` is bootstrapped (per D-011); for v0.1 the
bundled copy is the only source.
"""

from __future__ import annotations

from importlib import resources


def load_template(name: str) -> str:
    """Load a bundled template by its path within this package.

    ``name`` is a forward-slash path relative to ``skl.templates`` -
    e.g. ``"standalone-skill.md"`` or ``"sidecars/m365.yaml"``.
    Raises :class:`FileNotFoundError` if the template is not in the bundle.
    """
    parts = name.split("/")
    target = resources.files("skl.templates")
    for part in parts:
        target = target.joinpath(part)
    return target.read_text()


def render(template: str, **placeholders: str) -> str:
    """Substitute ``{{KEY}}`` markers with the matching keyword values."""
    out = template
    for key, value in placeholders.items():
        out = out.replace("{{" + key + "}}", value)
    return out
