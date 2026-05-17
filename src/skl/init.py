"""Implementation of `skl init` (global form): scaffold a new skill-host repo.

Per docs/spec/cli.md §`skl init` global form. The spec calls for
`skl shared sync` to be invoked internally after writing the manifest, but
that command is not yet implemented; this implementation emits a stderr
warning and leaves `_shared/` un-fetched. `shared_kit.pinned_sha` is omitted
from the manifest until the first real sync.
"""

from __future__ import annotations

import re
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from textwrap import dedent

from skl import __version__

DEFAULT_SHARED_KIT_SOURCE = "github.com/danielithomas/ai-skills-shared"
DEFAULT_SHARED_KIT_VERSION = "latest"

REPO_NAME_PATTERN = re.compile(r"^[a-z][a-z0-9-]{0,62}$")


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

    print(
        "warning: `skl shared sync` is not yet implemented; `_shared/` was not "
        "fetched and `shared_kit.pinned_sha` is absent from the manifest. "
        "Re-run `skl shared sync` once that command lands.",
        file=sys.stderr,
    )

    if not no_git:
        subprocess.run(
            ["git", "init", "--quiet", str(target)],
            check=True,
            stdout=subprocess.DEVNULL,
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
