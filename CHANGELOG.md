# Changelog

All notable changes to `skl` are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

### Added
- `skl shared sync`: fetches the shared kit per D-011. Repo-scoped form reads `shared_kit.source` / `shared_kit.version` from `skill-repo.yaml` (resolving the `"latest"` sentinel against the source's git tags) and writes the kit into `./_shared/`. Global form takes `--source`, `--version`, and `--to`. In both forms: any pre-existing `_shared/local/` overlay survives the sync, the resolved short SHA is recorded as `shared_kit.pinned_sha`, and `_shared/.kit_version` is written.
- `skl.manifest` module providing ruamel.yaml-backed `load` / `save` / `set_shared_kit_fields` helpers. Round-trip preservation of user-authored comments and formatting.
- `skl.shared` module with `sync_repo_scoped`, `sync_global`, source-URL normalisation (`github.com/<org>/<repo>` -> `https://github.com/<org>/<repo>.git`), and latest-tag resolution.
- `ruamel.yaml>=0.18` dependency.
- `skl init <name>` global form: scaffolds a new skill-host repo at `./<name>` with `skill-repo.yaml`, `README.md`, `LICENSE`, `.gitignore`, an empty `skills/` directory, and (unless `--no-git`) a `git init`. Accepts `--shared-kit-source` and `--shared-kit-version` flags. Refuses to run from inside an existing skill-host repo (the repo-scoped form is not yet implemented).
- `skl.init` module exporting `init_repo`, `find_skill_repo_root`, and `compatible_version_range` for reuse by other verbs.

### Changed
- `skl init` now invokes `skl shared sync` internally (per the spec). If the sync fails (e.g. the source URL is unreachable), the scaffold still succeeds and a stderr warning instructs the user to re-run `skl shared sync` once the source is reachable. Removes the stale "shared sync not yet implemented" warning.
- Initial scaffold: package metadata, `--version`, click-based CLI surface with stub verbs.
- `docs/spec/` covering CLI surface, `skill-repo.yaml` manifest, infrastructure, values + secrets, and compilation.
- `docs/decisions/` covering D-007 (three-tier values), D-008 (secrets separation), D-009 (multi-repo architecture), D-010 (toolkit identity), D-011 (shared kit fetched).
- README opens with the `skl` vs `skillctl` distinction (per D-010 follow-up #8).
- CI workflow on push / PR: ruff lint + format check, pytest, CLI smoke.

### Changed
- `cli.md` §`skl init` global form: `--shared-kit-source` and `--shared-kit-version` flags added with documented defaults, order of operations made explicit (write manifest, then sync), so `skl init` no longer has a chicken-and-egg dependency on a manifest that does not yet exist.
- `infrastructure.md`: advisory concurrency lock renamed `.skl.lock` → `.skl-process.lock` to remove the one-letter-apart collision with `skl.lock` (cross-repo deps lock).
- `manifest.md`: `secrets.backend` override removed; per-machine overrides belong in `_shared/local/skill.config.yaml` per D-008 + D-011, not in the committed manifest.
- `decisions/README.md`: softened the "D-001 to D-006 live in the parent project only" claim and added a "Parent decisions referenced by this spec" table covering D-001 / D-002 / D-004 / D-006.
- `D-011`: clarified `pinned_sha` is auto-written by `skl shared sync` and must not be hand-edited.
- `README.md` Quickstart: dropped the standalone `skl shared sync` call since `skl init` (global) now explicitly runs it.

### Status
- Pre-v0.1. The CLI surface is wired; verbs raise `NotImplementedError` with a pointer to the spec.

[Unreleased]: https://github.com/danielithomas/skl/compare/HEAD...HEAD
