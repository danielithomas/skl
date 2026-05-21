# Changelog

All notable changes to `skl` are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

### Added

Stage 1 (authoring foundation) - schemas, parsing, full `skl validate`, repo-scoped `skl init`, `skl lint`. See [docs/plan.md](docs/plan.md) for the v0.1 roadmap.

- **Bundled schemas** under `src/skl/schemas/` per [SKL-004](docs/decisions/SKL-004-master-skill-md-posture.md) and [SKL-009](docs/decisions/SKL-009-m365-schema-versioning.md): `skill.frontmatter.schema.json` (Anthropic base + `skl:` block), `platforms/{copilot-studio,m365,vscode}.schema.json` (sidecar input), `platforms/m365/declarative-agent-manifest-1.7.json` (M365 compiled-output baseline), `platforms/m365/index.json` (kit version index). `skl.schemas.load_schema(name)` for nested-path access.
- **`skl.skill_md`** module - parses SKILL.md into a `Skill` dataclass (full frontmatter, intro, ordered H2 sections; case-insensitive section lookup; H2 lines inside fenced code blocks ignored).
- **`skl.sidecars`** module - reads `<skill_root>/skl/platforms/*.yaml` into a `Sidecars` dataclass keyed by platform ID.
- **`skl.manifest`** gains `loads(text)` (string input for SKILL.md frontmatter) and `to_plain(obj)` (ruamel → plain dict/list). Single point of YAML access per CLAUDE.md.
- **`skl validate`** now runs the seven implemented check families (`manifest`, `frontmatter`, `body`, `sidecars`, `knowledge-contracts`, `values-declarations`, `shared-kit-drift`, `compatibility`). Cross-repo dependency verification remains deferred. The `body` check enforces required H2 sections per [SKL-008](docs/decisions/SKL-008-persona-defaults-skills-format-refresh.md); the `sidecars` check validates each `skl/platforms/<id>.yaml` and cross-references binding IDs against `skl.knowledge[]` / `skl.tools[]` declarations.
- **`skl init <skill-name>` repo-scoped form** - scaffolds `<repo>/skills/<name>/SKILL.md` from a bundled template under `src/skl/templates/`. `--platform <id>` is repeatable; sidecar stubs are emitted for `copilot-studio` / `m365` / `vscode`. M365's `schema_version` is templated from the bundled kit's `platforms/m365/index.json` default.
- **`skl lint`** - new verb. Five rule families on SKILL.md and sidecar files: `em-dash` (error), `au-spelling` (warning), `credentials/<vendor>` (error; AWS / Anthropic / OpenAI / GitHub / GitLab / Slack tokens and PRIVATE KEY blocks), `banned-phrase` (warning), `unresolved-token` (warning). `--fix` auto-applies em-dash and AU-spelling fixes in place; the fix model is per-occurrence substring replacement so multiple findings compose without overlap.
- `SKL_IGNORE_COMPAT` environment variable as a loud escape hatch for the compatibility guard. Set to `1` / `true` / `yes` / `on` (case-insensitive) to bypass the version-range check for one session; every command emits a stderr warning when the variable is set, including commands the guard would have passed. The escape hatch does **not** bypass manifest parse failure. See [SKL-010](docs/decisions/SKL-010-compat-guard-edge-cases.md).
- `skl.validate.GuardCheck` dataclass and `check_compatibility_status(repo_root)` returning a tagged result (`ok` / `mismatch` / `parse_error`). Replaces the previous `check_compatibility_or_message` wrapper.
- Global `skl_version` compatibility guard at the CLI entry point (`skl.cli.main`). Every invocation from inside a skill-host repo runs the guard before the subcommand dispatches; failures exit 4 per the spec. Skip list: `init`, `validate`. See [SKL-003](docs/decisions/SKL-003-global-compatibility-guard.md).

### Changed
- Compatibility guard now fails fast (exit 4) when `skill-repo.yaml` exists but cannot be parsed as YAML, with a message pointing at `skl validate`. Previously the guard silently no-oped on parse failure; the new behaviour gives a clearer next step than the downstream error users were hitting. See [SKL-010](docs/decisions/SKL-010-compat-guard-edge-cases.md).
- `skl.validate.check_compatibility_or_message` removed in favour of `check_compatibility_status` (see Added). Internal API; no external callers.
- `docs/open-questions.md` - live log of unresolved questions with `Q-NNN` IDs. Resolved questions stay forever with a strikethrough heading and a link to the deciding `SKL-NNN`.
- `docs/decisions/SKL-001` (drift is warning), `SKL-002` (unimplemented flags raise NIE), `SKL-003` (global compatibility guard). New `SKL-NNN` prefix for repo-local decisions; existing parent-mirrored decisions keep their `D-NNN` prefix.
- `skl validate`: runs the implemented check families (manifest schema, skl version compatibility, shared-kit drift) and reports the remaining spec checks (frontmatter, body, knowledge-contracts, cross-repo-dependencies, values-declarations) as `skipped` with a clear reason until SKILL.md scaffolding lands. Exit codes match the spec: 0 ok, 1 validation failure, 4 compatibility failure.
- `skl.schemas` package shipping `skill-repo.schema.json`, a JSON Schema for `skill-repo.yaml` enforcing required fields, kebab `name` pattern, visibility enum, the six known platforms, and structural shape of `shared_kit` / `cross_repo_dependencies[]`.
- `skl.validate` module exposing `validate_repo(repo_root)` returning a `ValidationReport`, plus `CheckResult` and `exit_code()` helpers. Each check family is a discrete function so future PRs can wire in the deferred checks without restructuring.
- `jsonschema>=4.21` and `packaging>=24.0` dependencies (jsonschema for manifest + future frontmatter validation; packaging for `skl_version` specifier-set matching).

### Changed
- `skl validate --skill <name>` / `--all` now raise `NotImplementedError` instead of silently accepting the flag with a stderr note. Matches the convention used by every unbuilt verb. See [SKL-002](docs/decisions/SKL-002-unimplemented-flags-error.md).
- `docs/spec/infrastructure.md` §Skill-host repo compatibility: documented the exempt subcommands (`init`, `validate`) with a pointer to SKL-003.
- `docs/decisions/README.md`: distinguished `D-NNN` (parent-mirrored) from `SKL-NNN` (local) prefixes; pointed the process discussion at the new open-questions workflow.
- `CLAUDE.md`: added an "Open questions and decisions" section describing the `Q-NNN` / `SKL-NNN` workflow.

### Documentation
- `CLAUDE.md` Working conventions: all YAML access goes through `skl.manifest`; do not import `ruamel.yaml` / `yaml` directly elsewhere.
- `docs/spec/manifest.md`: documented the `"latest"` sentinel value for `shared_kit.version`, with a "what it means and when sync resolves it" section.
- `docs/spec/cli.md` §`skl init`: documented the non-fatal sync-failure path - init exits 0 with a stderr warning when the kit fetch fails, so users can scaffold offline / before configuring auth.

### Fixed
- `skl shared sync`: silence cosmetic git output (`Note: switching to ... detached HEAD`, `warning: --depth is ignored in local clones`). Detached-HEAD advice is suppressed via `-c advice.detachedHead=false`; `--depth 1` is skipped when the source resolves to a local filesystem path.

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
