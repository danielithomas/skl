"""Top-level CLI for skl.

The CLI surface is specified in docs/spec/cli.md. Implemented verbs dispatch
to the corresponding module under ``src/skl/``; verbs that have not yet been
built raise ``NotImplementedError`` with a pointer back to the spec.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import click

from skl import __version__
from skl.init import (
    DEFAULT_SHARED_KIT_SOURCE,
    DEFAULT_SHARED_KIT_VERSION,
    find_skill_repo_root,
    init_repo,
)
from skl.shared import sync_global, sync_repo_scoped

SPEC_REFERENCE = "See docs/spec/cli.md for the planned behaviour."


@click.group(
    context_settings={"help_option_names": ["-h", "--help"]},
    help="Skill build and multi-platform deployment tool.",
)
@click.version_option(version=__version__, prog_name="skl")
def main() -> None:
    """skl CLI entry point."""


@main.command()
@click.argument("name")
@click.option(
    "--shared-kit-source",
    default=DEFAULT_SHARED_KIT_SOURCE,
    show_default=True,
    help="Written into shared_kit.source in the new manifest.",
)
@click.option(
    "--shared-kit-version",
    default=DEFAULT_SHARED_KIT_VERSION,
    show_default=True,
    help="Written into shared_kit.version. Resolved by `skl shared sync` when that command lands.",
)
@click.option("--no-git", is_flag=True, help="Skip `git init` on the new directory.")
def init(name: str, shared_kit_source: str, shared_kit_version: str, no_git: bool) -> None:
    """Scaffold a new skill-host repo (global form) at ./<name>.

    The repo-scoped form (scaffolding a new skill inside an existing repo) is
    not implemented yet; this command refuses to run from inside a skill-host
    repo to avoid accidental nesting.
    """
    cwd = Path.cwd()
    if find_skill_repo_root(cwd) is not None:
        raise click.ClickException(
            "you are inside an existing skill-host repo; the repo-scoped form of "
            "`skl init` is not yet implemented. cd out before scaffolding a new repo."
        )
    target = cwd / name
    try:
        init_repo(
            target,
            shared_kit_source=shared_kit_source,
            shared_kit_version=shared_kit_version,
            no_git=no_git,
        )
    except (ValueError, FileExistsError) as exc:
        raise click.ClickException(str(exc)) from exc
    click.echo(f"scaffolded skill-host repo at {target}")


@main.command()
@click.option("--all", "all_", is_flag=True, help="Validate every skill in the repo.")
def validate(all_: bool) -> None:
    """Validate frontmatter, body, knowledge contracts, references and shared-kit drift."""
    raise NotImplementedError(f"skl validate is not implemented yet. {SPEC_REFERENCE}")


@main.command()
@click.option("--all", "all_", is_flag=True, help="Compile every skill in the repo.")
def compile(all_: bool) -> None:
    """Compile SKILL.md to enabled platform artefacts under platforms/."""
    raise NotImplementedError(f"skl compile is not implemented yet. {SPEC_REFERENCE}")


@main.command()
@click.option("--all", "all_", is_flag=True, help="Check budget for every skill.")
def budget(all_: bool) -> None:
    """Report character usage versus per-platform budget (8K for Copilot Studio)."""
    raise NotImplementedError(f"skl budget is not implemented yet. {SPEC_REFERENCE}")


@main.command()
@click.option("--all", "all_", is_flag=True, help="Test every skill.")
@click.option("--mock", is_flag=True, help="Use mocked platform responses.")
def test(all_: bool, mock: bool) -> None:
    """Run fixtures against compiled artefacts."""
    raise NotImplementedError(f"skl test is not implemented yet. {SPEC_REFERENCE}")


@main.command()
def index() -> None:
    """Regenerate skills/SKILLS_INDEX.md from the current skill set."""
    raise NotImplementedError(f"skl index is not implemented yet. {SPEC_REFERENCE}")


@main.command()
@click.option("--all", "all_", is_flag=True, help="Lint every skill in the repo.")
@click.option("--fix", is_flag=True, help="Auto-fix where possible.")
def lint(all_: bool, fix: bool) -> None:
    """Style enforcement: em-dashes, AU spellings, unresolved tokens, credential-shaped strings."""
    raise NotImplementedError(f"skl lint is not implemented yet. {SPEC_REFERENCE}")


@main.command()
@click.option("--skill", required=True, help="Skill kebab name.")
@click.option("--platform", "platform_", required=True, help="Target platform identifier.")
def deploy(skill: str, platform_: str) -> None:
    """Substitute values and copy the compiled artefact to its install location."""
    raise NotImplementedError(f"skl deploy is not implemented yet. {SPEC_REFERENCE}")


@main.command()
@click.argument("name")
@click.option("--in-favour-of", "in_favour_of", help="Replacement skill.")
def deprecate(name: str, in_favour_of: str | None) -> None:
    """Mark a skill as deprecated."""
    raise NotImplementedError(f"skl deprecate is not implemented yet. {SPEC_REFERENCE}")


@main.command()
@click.argument("legacy_path", type=click.Path(exists=True))
def migrate(legacy_path: str) -> None:
    """Scaffold a SKILL.md draft from a legacy agent file (in-repo only)."""
    raise NotImplementedError(f"skl migrate is not implemented yet. {SPEC_REFERENCE}")


@main.group()
def shared() -> None:
    """Shared-kit operations."""


@shared.command("sync")
@click.option(
    "--version",
    "version_",
    help="Pin or override the shared-kit version. In repo-scoped form, defaults to the manifest value.",
)
@click.option(
    "--source",
    "source_",
    help="(global form) Shared-kit source URL or `github.com/<org>/<repo>` shorthand.",
)
@click.option(
    "--to",
    "to_",
    type=click.Path(path_type=Path),
    help="(global form) Write the kit to this path instead of ./_shared/.",
)
def shared_sync(version_: str | None, source_: str | None, to_: Path | None) -> None:
    """Fetch the shared kit and write it into ./_shared/ (or to --to)."""
    if to_ is not None:
        if source_ is None or version_ is None:
            raise click.ClickException("global form (--to) requires both --source and --version")
        try:
            resolved_version, sha = sync_global(source=source_, version=version_, target=to_)
        except (subprocess.CalledProcessError, RuntimeError, ValueError) as exc:
            raise click.ClickException(str(exc)) from exc
        click.echo(f"synced {source_}@{resolved_version} ({sha}) to {to_}")
        return

    repo_root = find_skill_repo_root(Path.cwd())
    if repo_root is None:
        raise click.ClickException("not inside a skill-host repo")
    try:
        resolved_version, sha = sync_repo_scoped(repo_root, version=version_)
    except (subprocess.CalledProcessError, RuntimeError, ValueError) as exc:
        raise click.ClickException(str(exc)) from exc
    click.echo(f"synced shared kit @ {resolved_version} ({sha}) into {repo_root}/_shared/")


@main.group()
def values() -> None:
    """Values-file operations."""


@values.command("check")
@click.option("--values-file", "values_file", type=click.Path(), help="Values file to check.")
def values_check(values_file: str | None) -> None:
    """Verify all required vars are supplied and reject secret-like keys."""
    raise NotImplementedError(f"skl values check is not implemented yet. {SPEC_REFERENCE}")


@values.command("sync")
@click.option("--from", "from_", required=True, help="Source path or git URL.")
@click.option("--profile", help="Named profile within the source.")
def values_sync(from_: str, profile: str | None) -> None:
    """Sync a values profile from the sibling private values repo into ./.values/."""
    raise NotImplementedError(f"skl values sync is not implemented yet. {SPEC_REFERENCE}")


@values.command("schema")
@click.option("--output", type=click.Path(), help="Where to write the generated schema.")
def values_schema(output: str | None) -> None:
    """Generate a JSON Schema from the union of all enabled skills' variables."""
    raise NotImplementedError(f"skl values schema is not implemented yet. {SPEC_REFERENCE}")


@main.group()
def secrets() -> None:
    """Secrets-backend operations."""


@secrets.command("get")
@click.argument("key")
def secrets_get(key: str) -> None:
    """Resolve a secret via the configured backend."""
    raise NotImplementedError(f"skl secrets get is not implemented yet. {SPEC_REFERENCE}")


@secrets.command("set")
@click.argument("key")
def secrets_set(key: str) -> None:
    """Write a secret to the configured backend (where supported)."""
    raise NotImplementedError(f"skl secrets set is not implemented yet. {SPEC_REFERENCE}")


@secrets.command("list")
def secrets_list() -> None:
    """Enumerate known secret keys without revealing values."""
    raise NotImplementedError(f"skl secrets list is not implemented yet. {SPEC_REFERENCE}")


if __name__ == "__main__":
    main()
