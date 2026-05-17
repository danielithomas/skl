"""Implementation of ``skl shared sync``: fetch the shared kit per D-011.

Repo-scoped form reads ``shared_kit.source`` and ``shared_kit.version`` from
``skill-repo.yaml`` and writes the kit to ``./_shared/``. Global form takes
``--source`` and ``--version`` on the CLI and writes to an arbitrary path.

In both forms: the fetch is a ``git clone`` (subprocess), the resolved short
SHA is recorded, any pre-existing ``_shared/local/`` overlay is preserved
across the sync, and ``_shared/.kit_version`` is written.
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

from skl import manifest as _manifest

SHORT_SHA_LENGTH = 12
LATEST_VERSION_SENTINEL = "latest"


def sync_repo_scoped(repo_root: Path, *, version: str | None = None) -> tuple[str, str]:
    """Sync the shared kit into ``<repo_root>/_shared/``.

    Reads source / version from ``<repo_root>/skill-repo.yaml``. If ``version``
    is given, overrides the manifest version (and is written back). The
    resolved version (``"latest"`` becomes a real tag) and short SHA are
    written back into the manifest, and ``_shared/.kit_version`` is written.

    Returns the resolved ``(version, sha)`` for caller convenience.
    """
    manifest_path = repo_root / "skill-repo.yaml"
    data = _manifest.load(manifest_path)
    shared_kit = data.get("shared_kit") or {}
    source = shared_kit.get("source")
    if not source:
        raise ValueError(f"{manifest_path} has no shared_kit.source")
    if version is None:
        version = shared_kit.get("version")
    if not version:
        raise ValueError(f"{manifest_path} has no shared_kit.version")

    target = repo_root / "_shared"
    resolved_version, resolved_sha = _fetch_and_copy(source, version, target)

    _manifest.set_shared_kit_fields(
        manifest_path,
        version=resolved_version,
        pinned_sha=resolved_sha,
    )
    (target / ".kit_version").write_text(f"{resolved_version}\n")

    return resolved_version, resolved_sha


def sync_global(*, source: str, version: str, target: Path) -> tuple[str, str]:
    """Sync to an arbitrary target path. Returns the resolved ``(version, sha)``.

    Also writes ``<target>/.kit_version`` so the same drift-detection works.
    """
    resolved_version, resolved_sha = _fetch_and_copy(source, version, target)
    (target / ".kit_version").write_text(f"{resolved_version}\n")
    return resolved_version, resolved_sha


def _fetch_and_copy(source: str, version: str, target: Path) -> tuple[str, str]:
    """Clone ``source`` at ``version``, copy files into ``target``.

    Returns ``(resolved_version, short_sha)``. ``resolved_version`` equals
    ``version`` unless the input was the ``"latest"`` sentinel, in which
    case it is the highest semver tag in the cloned repo.
    """
    url = _normalise_source(source)

    with tempfile.TemporaryDirectory() as tmpdir_str:
        tmpdir = Path(tmpdir_str)
        kit_clone = tmpdir / "kit"

        if version == LATEST_VERSION_SENTINEL:
            _run_git("clone", "--quiet", url, str(kit_clone))
            resolved_version = _latest_tag(kit_clone)
            if resolved_version is None:
                raise RuntimeError(f"shared kit at {source} has no tags; cannot resolve 'latest'")
            _run_git("-C", str(kit_clone), "checkout", "--quiet", resolved_version)
        else:
            _run_git(
                "clone",
                "--quiet",
                "--depth",
                "1",
                "--branch",
                version,
                url,
                str(kit_clone),
            )
            resolved_version = version

        full_sha = _run_git_capture("-C", str(kit_clone), "rev-parse", "HEAD")
        short_sha = full_sha[:SHORT_SHA_LENGTH]

        _copy_kit_to_target(kit_clone, target, tmpdir)

    return resolved_version, short_sha


def _normalise_source(source: str) -> str:
    """Convert a ``github.com/<org>/<repo>`` shorthand to a clone URL.

    Accepts the spec's shorthand and any well-formed git URL untouched.
    """
    if source.startswith(("http://", "https://", "git@", "git://", "ssh://")):
        return source
    if source.startswith("github.com/"):
        return f"https://{source}.git"
    # Could be a local path or an unknown shorthand; pass through.
    return source


def _latest_tag(repo: Path) -> str | None:
    """Return the highest semver tag in ``repo``, or None if none exist."""
    tags_output = _run_git_capture("-C", str(repo), "tag", "--list", "--sort=-v:refname")
    tags = [t.strip() for t in tags_output.splitlines() if t.strip()]
    return tags[0] if tags else None


def _copy_kit_to_target(kit_dir: Path, target: Path, scratch: Path) -> None:
    """Replace ``target/`` contents with ``kit_dir/`` (sans .git), preserving ``target/local/``."""
    preserved_local: Path | None = None
    if (target / "local").exists():
        preserved_local = scratch / "preserved-local"
        shutil.copytree(target / "local", preserved_local)

    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True)

    for item in kit_dir.iterdir():
        if item.name == ".git":
            continue
        destination = target / item.name
        if item.is_dir():
            shutil.copytree(item, destination)
        else:
            shutil.copy2(item, destination)

    if preserved_local is not None:
        shutil.copytree(preserved_local, target / "local")


def _run_git(*args: str) -> None:
    """Run ``git <args>`` with check=True; let CalledProcessError propagate."""
    subprocess.run(["git", *args], check=True)


def _run_git_capture(*args: str) -> str:
    """Run ``git <args>`` capturing stdout. Returns stripped stdout text."""
    result = subprocess.run(["git", *args], check=True, capture_output=True, text=True)
    return result.stdout.strip()
