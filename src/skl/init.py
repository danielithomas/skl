"""Implementation of ``skl init`` in both forms.

Global form (existing): scaffold a new skill-host repo. See
:func:`init_repo` and ``docs/spec/cli.md`` §``skl init`` global form.

Repo-scoped form (this module's :func:`init_skill`): scaffold a new
skill inside an existing skill-host repo. The CLI dispatches between
the two based on whether the cwd is inside a skill-host repo.
"""

from __future__ import annotations

import re
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from textwrap import dedent

from skl import __version__, shared
from skl.schemas import load_schema
from skl.templates import load_template, render

DEFAULT_SHARED_KIT_SOURCE = "github.com/danielithomas/ai-skills-shared"
DEFAULT_SHARED_KIT_VERSION = "latest"

REPO_NAME_PATTERN = re.compile(r"^[a-z][a-z0-9-]{0,62}$")
SKILL_NAME_PATTERN = re.compile(r"^[a-z][a-z0-9-]{0,63}$")

# Platforms recognised in `enabled_platforms` (matches both the manifest
# schema and the SKILL.md frontmatter schema).
_KNOWN_PLATFORMS: frozenset[str] = frozenset(
    {"copilot-studio", "m365", "ms-cowork", "claude-code", "claude-cowork", "vscode"}
)

# Skills-native targets need no sidecar (compile is essentially a copy).
_SIDECAR_PLATFORMS: frozenset[str] = frozenset({"copilot-studio", "m365", "vscode"})


def init_repo(
    target: Path,
    *,
    shared_kit_source: str = DEFAULT_SHARED_KIT_SOURCE,
    shared_kit_version: str = DEFAULT_SHARED_KIT_VERSION,
    no_git: bool = False,
) -> None:
    """Scaffold a new skill-host repo at ``target``.

    Parameters
    ----------
    target:
        Directory to create. Its basename is used as the repo ``name`` and
        must match ``^[a-z][a-z0-9-]{0,62}$`` (the manifest schema rule).
    shared_kit_source:
        Written into ``shared_kit.source`` in the manifest.
    shared_kit_version:
        Written into ``shared_kit.version`` in the manifest. The default
        sentinel ``"latest"`` is resolved by ``skl shared sync`` once that
        command lands.
    no_git:
        If ``True``, skip ``git init`` on the new directory.
    """
    name = target.name
    if not REPO_NAME_PATTERN.match(name):
        raise ValueError(
            f"repo name {name!r} must match {REPO_NAME_PATTERN.pattern} "
            "(kebab-case, leading letter, max 63 chars)"
        )
    if target.exists():
        raise FileExistsError(f"target path already exists: {target}")

    target.mkdir(parents=True)
    (target / "skills").mkdir()

    _write_manifest(target / "skill-repo.yaml", name, shared_kit_source, shared_kit_version)
    _write_readme(target / "README.md", name)
    _write_license(target / "LICENSE")
    _write_gitignore(target / ".gitignore")

    _try_shared_sync(target)

    if not no_git:
        subprocess.run(
            ["git", "init", "--quiet", str(target)],
            check=True,
            stdout=subprocess.DEVNULL,
        )


def _try_shared_sync(target: Path) -> None:
    """Call shared.sync_repo_scoped, swallowing fetch failures with a clear warning.

    The spec calls for sync to run internally during ``skl init``. We treat a
    sync failure as a recoverable warning (not a hard error) so the user is
    left with a usable scaffold they can finish setting up out of band.
    """
    try:
        resolved_version, sha = shared.sync_repo_scoped(target)
    except (subprocess.CalledProcessError, RuntimeError, ValueError, OSError) as exc:
        print(
            f"warning: shared sync failed: {exc}. "
            f"Repo is scaffolded; run `skl shared sync` once the source is reachable.",
            file=sys.stderr,
        )
        return
    print(
        f"fetched shared kit @ {resolved_version} ({sha}) into {target}/_shared/",
        file=sys.stderr,
    )


def compatible_version_range(version: str = __version__) -> str:
    """Return a manifest-friendly ``skl_version`` range for the running version.

    Below 1.0, pins to the current minor (``>=0.0.1,<0.1``). At or above 1.0,
    pins to the current major (``>=1.0,<2.0``). Mirrors the example ranges in
    ``docs/spec/manifest.md`` once the package reaches v1.
    """
    parts = version.split(".")
    if len(parts) < 2:
        raise ValueError(f"unparseable __version__: {version!r}")
    major = int(parts[0])
    minor = int(parts[1])
    if major == 0:
        return f">={version},<{major}.{minor + 1}"
    return f">={major}.0,<{major + 1}.0"


def _write_manifest(path: Path, name: str, source: str, version: str) -> None:
    """Write skill-repo.yaml with sensible defaults for a fresh skill-host repo."""
    content = dedent(f"""\
        # Manifest for the {name} skill-host repo.
        # Schema: docs/spec/manifest.md in the skl repo.

        schema_version: 1
        name: {name}
        visibility: internal
        skl_version: "{compatible_version_range()}"

        shared_kit:
          source: {source}
          version: "{version}"
          # pinned_sha is written by `skl shared sync`; do not hand-edit.

        enabled_platforms: []
        cross_repo_dependencies: []

        defaults:
          output_language: en-AU
        """)
    path.write_text(content)


def _write_readme(path: Path, name: str) -> None:
    """Write a minimal README; the user is expected to expand it."""
    content = dedent(f"""\
        # {name}

        Skill-host repo scaffolded by `skl init`.

        See `skill-repo.yaml` for the manifest. See [skl](https://github.com/danielithomas/skl)
        for the CLI that compiles, validates and deploys the skills in this repo.

        ## Getting started

        ```bash
        skl shared sync          # fetch the shared kit into ./_shared/
        skl init <skill-name>    # scaffold a new skill under ./skills/
        skl validate             # check manifest, skill frontmatter, contracts
        ```
        """)
    path.write_text(content)


def _write_license(path: Path) -> None:
    """Write an MIT licence with a placeholder copyright holder.

    The user is expected to replace ``<copyright holder>`` and the year if
    they want anything different.
    """
    year = datetime.now(UTC).year
    content = dedent(f"""\
        MIT License

        Copyright (c) {year} <copyright holder>

        Permission is hereby granted, free of charge, to any person obtaining a copy
        of this software and associated documentation files (the "Software"), to deal
        in the Software without restriction, including without limitation the rights
        to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
        copies of the Software, and to permit persons to whom the Software is
        furnished to do so, subject to the following conditions:

        The above copyright notice and this permission notice shall be included in all
        copies or substantial portions of the Software.

        THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
        IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
        FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
        AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
        LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
        OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
        SOFTWARE.
        """)
    path.write_text(content)


def _write_gitignore(path: Path) -> None:
    """Write a .gitignore covering the artefacts skl produces that should not be committed."""
    content = dedent("""\
        # skl runtime
        .values/
        .skl-process.lock
        values.schema.json

        # Python
        __pycache__/
        *.py[cod]
        *.egg-info/
        .venv/
        .pytest_cache/
        .ruff_cache/

        # OS / editor
        .DS_Store
        Thumbs.db
        .idea/
        .vscode/
        """)
    path.write_text(content)


def find_skill_repo_root(start: Path) -> Path | None:
    """Walk up from ``start`` looking for ``skill-repo.yaml``; return the dir or None.

    First match wins, per docs/spec/infrastructure.md §Repo discovery.
    """
    for candidate in [start, *start.parents]:
        if (candidate / "skill-repo.yaml").is_file():
            return candidate
    return None


# ---------------------------------------------------------------------------
# Repo-scoped form: scaffold a skill inside an existing skill-host repo
# ---------------------------------------------------------------------------


def init_skill(
    repo_root: Path,
    skill_name: str,
    *,
    platforms: tuple[str, ...] = (),
) -> Path:
    """Scaffold ``<repo_root>/skills/<skill_name>/`` from the bundled template.

    Parameters
    ----------
    repo_root:
        Skill-host repo root (containing ``skill-repo.yaml``).
    skill_name:
        Kebab-case skill identifier; becomes the folder name and the
        SKILL.md ``name`` field.
    platforms:
        Platform IDs the new skill targets. Lands in ``skl.enabled_platforms``;
        sidecar stubs are also written for any of ``{copilot-studio, m365,
        vscode}`` requested. Skills-native targets (``claude-code`` /
        ``claude-cowork`` / ``ms-cowork``) need no sidecar.

    Returns the path to the new skill folder.

    Raises ``ValueError`` for a bad skill name or unknown platform IDs,
    ``FileExistsError`` if the target folder already exists.
    """
    if not SKILL_NAME_PATTERN.match(skill_name):
        raise ValueError(
            f"skill name {skill_name!r} must match {SKILL_NAME_PATTERN.pattern} "
            "(kebab-case, leading letter, max 64 chars)"
        )
    unknown = [p for p in platforms if p not in _KNOWN_PLATFORMS]
    if unknown:
        raise ValueError(
            f"unknown platform(s): {', '.join(sorted(set(unknown)))}. "
            f"Known: {', '.join(sorted(_KNOWN_PLATFORMS))}"
        )

    skill_root = repo_root / "skills" / skill_name
    if skill_root.exists():
        raise FileExistsError(f"skill folder already exists: {skill_root}")

    skill_root.mkdir(parents=True)
    _write_skill_md(skill_root / "SKILL.md", skill_name, platforms)
    sidecars_written = _write_sidecars(skill_root, platforms)
    if sidecars_written:
        print(
            f"scaffolded {skill_root.relative_to(repo_root)}/ with sidecars: "
            f"{', '.join(sidecars_written)}",
            file=sys.stderr,
        )
    else:
        print(f"scaffolded {skill_root.relative_to(repo_root)}/", file=sys.stderr)
    return skill_root


def kebab_to_display_name(name: str) -> str:
    """Convert ``casey-case-studies`` to ``Casey Case Studies`` for the H1 / display_name."""
    return " ".join(part.capitalize() for part in name.split("-") if part)


def _write_skill_md(path: Path, skill_name: str, platforms: tuple[str, ...]) -> None:
    template = load_template("standalone-skill.md")
    display_name = kebab_to_display_name(skill_name)
    enabled_platforms_yaml = ", ".join(platforms)
    rendered = render(
        template,
        NAME=skill_name,
        DISPLAY_NAME=display_name,
        ENABLED_PLATFORMS=enabled_platforms_yaml,
    )
    path.write_text(rendered)


def _write_sidecars(skill_root: Path, platforms: tuple[str, ...]) -> list[str]:
    """Write a sidecar stub for each requested non-Skills-native platform."""
    needed = [p for p in platforms if p in _SIDECAR_PLATFORMS]
    if not needed:
        return []
    sidecars_dir = skill_root / "skl" / "platforms"
    sidecars_dir.mkdir(parents=True)
    for platform_id in needed:
        template = load_template(f"sidecars/{platform_id}.yaml")
        if platform_id == "m365":
            template = render(template, M365_SCHEMA_VERSION=_default_m365_schema_version())
        (sidecars_dir / f"{platform_id}.yaml").write_text(template)
    return needed


def _default_m365_schema_version() -> str:
    """Read the bundled M365 schema index's ``default`` per SKL-009."""
    index = load_schema("platforms/m365/index.json")
    default = index.get("default")
    if not isinstance(default, str):
        raise RuntimeError("bundled platforms/m365/index.json is missing a string `default` field")
    return default
