# CLI surface

This document specifies every verb of the `skl` CLI, its arguments, exit codes, and global behaviour. Distilled from the parent project's `analysis/03_convenience_scripts_spec.md` (D3) and `analysis/07_multi_repo_skill_architecture.md` §4 (D7).

---

## Global behaviour

### Invocation

```
skl [GLOBAL-OPTIONS] <COMMAND> [COMMAND-OPTIONS]
```

### Global options

| Option | Effect |
|--------|--------|
| `--version` | Print the package version and exit 0 |
| `-h, --help` | Print help and exit 0 |

### Repo discovery

`skl` walks up from the current working directory looking for `skill-repo.yaml`. The first match wins.

- If a `skill-repo.yaml` is found, the repo is the **active skill-host repo** and all commands operate on it by default.
- If no `skill-repo.yaml` is found, only the **global subset** of commands runs. Other commands fail with exit code 2 and the message `not inside a skill-host repo`.

### Global vs repo-scoped commands

| Command | Global | Repo-scoped |
|---------|--------|-------------|
| `skl --version` | yes | - |
| `skl --help` | yes | - |
| `skl init <name>` | yes (scaffolds a new repo) | yes (scaffolds a new skill in the active repo) |
| `skl shared sync --to <path>` | yes | - |
| `skl shared sync` | - | yes |
| All other verbs | - | yes |

### Exit codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Validation failure, test failure, or other domain error |
| 2 | Misuse: invalid arguments, not inside a skill-host repo, unknown command |
| 3 | Environment failure: missing dependency, unreadable filesystem, denied auth |
| 4 | Compatibility failure: installed `skl` version outside the manifest's `skl_version` range |

---

## Commands

### `skl init`

Scaffold a new skill-host repo (global form) or a new skill inside the active repo (repo-scoped form).

**Global form** - `skl init <repo-name> [--shared-kit-source <url>] [--shared-kit-version <semver>] [--no-git]`

Order of operations:

1. Create a directory named `<repo-name>`.
2. Write `skill-repo.yaml` with sensible defaults (visibility `internal`, current `skl` version range, no enabled platforms yet, `shared_kit.source` and `shared_kit.version` taken from the flags or their defaults).
3. Write `README.md`, `LICENSE`, `.gitignore` and create an empty `skills/` directory.
4. Run `skl shared sync` internally against the new manifest so the kit lands at `./_shared/` and the resolved `pinned_sha` is written back into the manifest. **If sync fails** (source unreachable, missing tag, auth required, network down), `skl init` logs a warning to stderr and continues with exit 0; the scaffolded files are still on disk and the user is expected to re-run `skl shared sync` once the source is reachable. This is intentional - it lets the user scaffold offline or before configuring auth to a private kit repo.
5. Run `git init` unless `--no-git` is passed.

Flags:

| Flag | Default | Notes |
|------|---------|-------|
| `--shared-kit-source` | `github.com/danielithomas/ai-skills-shared` | Written into `shared_kit.source` |
| `--shared-kit-version` | latest tag at fetch time | Written into `shared_kit.version` |
| `--no-git` | (off) | Skip `git init` |

**Repo-scoped form** - `skl init <skill-kebab-name> [--platform <id>]...`

Creates `skills/<skill-kebab-name>/SKILL.md` and (where applicable) per-platform sidecars. Dispatch between global and repo-scoped is based on the cwd: inside an existing skill-host repo the command runs the repo-scoped form; outside, it runs the global form.

Order of operations:

1. Validate the skill name against the kebab pattern (`^[a-z][a-z0-9-]{0,63}$`).
2. Validate any `--platform <id>` values against the known platform enum (`copilot-studio`, `m365`, `ms-cowork`, `claude-code`, `claude-cowork`, `vscode`).
3. Refuse if `skills/<skill-kebab-name>/` already exists.
4. Write `SKILL.md` from `<repo>/_shared/templates/standalone-skill.md` if present, falling back to the bundled copy in `src/skl/templates/`. `{{NAME}}` and `{{DISPLAY_NAME}}` are substituted; `{{ENABLED_PLATFORMS}}` is the comma-joined `--platform` list.
5. For each non-Skills-native `--platform` (`copilot-studio` / `m365` / `vscode`), write the matching sidecar stub at `skl/platforms/<id>.yaml`. The M365 stub's `schema_version` is read from the kit's `_shared/schemas/platforms/m365/index.json` `default` (falling back to the bundled copy) per [SKL-009](../decisions/SKL-009-m365-schema-versioning.md).
6. Skills-native platforms (`claude-code` / `claude-cowork` / `ms-cowork`) need no sidecar.

Flags:

| Flag | Default | Notes |
|------|---------|-------|
| `--platform <id>` | (none) | Repeatable. Lands in `skl.enabled_platforms` and triggers sidecar emission for non-Skills-native targets |

The global-form flags (`--shared-kit-source`, `--shared-kit-version`, `--no-git`) are accepted but warned if passed in the repo-scoped context. Conversely, `--platform` in the global form is a clear error.

---

### `skl validate`

Validate frontmatter, body, knowledge contracts, references, and shared-kit drift.

```
skl validate [--skill <kebab-name>] [--all]
```

Checks performed:
1. **Manifest** - `skill-repo.yaml` matches the documented schema.
2. **Frontmatter** - every SKILL.md's YAML frontmatter matches `skill.frontmatter.schema.json` (per [SKL-004](../decisions/SKL-004-master-skill-md-posture.md)). SKILL.md parse errors surface here.
3. **Body** - required H2 sections present per the platforms the skill targets (per [SKL-008](../decisions/SKL-008-persona-defaults-skills-format-refresh.md)). `## Capabilities`, `## Workflow`, `## Edge Cases`, `## Examples` are always required; `## Identity` is required for persona-surface targets (Copilot Studio; VS Code Custom Agent variant when the sidecar exists); `## Knowledge Sources` / `## Tools` are required when the matching declarations exist. Warns when H1 does not match `skl.display_name`.
4. **Knowledge contracts** - every `skl.knowledge[i].contract` resolves to an existing file relative to the skill root.
5. **Cross-repo dependencies** - entries in `cross_repo_dependencies[]` resolve at the pinned SHA. **Deferred in v0.1** (needs git access for pinned-SHA verification); surfaces as `skipped` with a clear reason.
6. **Shared-kit drift** - `_shared/.kit_version` matches `shared_kit.version` in the manifest; warns on divergent files.
7. **Values declarations** - every `{{variables.X}}` token in a SKILL.md body or sidecar must be declared in `skl.variables[]`.
8. **Compatibility** - the installed `skl` version is within the manifest's `skl_version` range.

In addition, the `sidecars` check (new in v0.1 per SKL-004) validates each `skl/platforms/<id>.yaml` against its bundled schema and cross-references every `bindings.knowledge.<id>` / `bindings.tools.<id>` against the master `skl.knowledge[]` / `skl.tools[]` declarations. Warns when `enabled_platforms` includes a non-Skills-native target with no sidecar but the skill declares bindings.

Exit codes: 0 (pass), 1 (validation failure), 4 (compatibility failure).

---

### `skl compile`

Compile each SKILL.md into platform-specific artefacts written under the repo's `platforms/<platform-id>/<skill>/` directory.

```
skl compile [--skill <kebab-name>] [--platform <platform-id>] [--all]
```

- **Default behaviour**: compile every skill for every platform in its `enabled_platforms`. The `--all` flag is accepted as a spec-compat no-op.
- `--skill <name>` filters to a single skill.
- `--platform <id>` filters to a single platform.
- For each `enabled_platforms` entry, the matching compiler in [`compilation.md`](./compilation.md) runs.
- Artefacts are written in **template form** (per D-007): `{{variables.x}}` and `{{knowledge.id}}` tokens remain unresolved. Substitution happens at deploy time, not compile time.
- The output is committed to the repo (D-001), giving non-developer colleagues a directly consumable build.
- Compile does **not** auto-run `skl validate` - run that yourself before compile if the manifest / SKILL.md is in flux. Compile-time errors will still surface for malformed input, but `skl validate` gives the full picture.

Stage status (per [`docs/plan.md`](../plan.md)):

- Skills-native compile for `claude-code` / `claude-cowork` / `ms-cowork` (Stage 2). One implementation, byte-identical output across the three, per SKL-006 + SKL-008.
- VS Code compile (Stage 3). Emits a Skill variant (byte-identical to `claude-code`) and/or a Custom Agent variant per SKL-007.
- Copilot Studio compile (Stage 4). 8K hard budget. Identity inlined as preamble; canonical-section composition; knowledge / tools tokens rewritten to `/<binding>` UI refs. See `compilation.md` for the section order and rewrite rules.
- M365 compile (Stage 4). Two-file output (`declarative-agent.json` + `instructions.md`); mandatory per-skill `schema_version` pin per SKL-009; compiled manifest validated against the bundled schema before write; 8K cap on the manifest's `instructions` field.

**All six v0.1 platforms now compile.**

Exit codes: 0 if no errors (skips allowed); 1 if any compiler errored.

---

### `skl budget`

Report compiled-instructions character usage versus per-platform budget caps.

```
skl budget [--all]
```

Walks every skill in the repo. For each enabled platform with a hard cap, computes the would-be compiled-instructions length and reports it as a row of a deterministic table:

```
Skill                           Platform           Used      Cap     %  Status
--------------------------------------------------------------------------------
casey-case-studies              copilot-studio    6,234    8,000   78%  ok
casey-case-studies              m365              5,891    8,000   74%  ok
big-skill                       copilot-studio    8,512    8,000  106%  OVER
```

Currently enforced budgets:

| Platform | Budget | Notes |
|----------|--------|-------|
| Copilot Studio | 8,000 chars | Hard limit imposed by the platform. Per-skill `budget:` in `skl/platforms/copilot-studio.yaml` can lower the cap |
| M365 Copilot | 8,000 chars | Hard limit on the manifest's `instructions` field |
| Skills-native (`claude-code`, `claude-cowork`, `ms-cowork`) | none | Uncapped; not measured |
| VS Code (Skill + Custom Agent) | none | Uncapped; not measured |

Skills whose SKILL.md fails to parse appear in a `skipped` footer rather than the main table - run `skl validate` to surface the parse error.

Exit 0 if every (skill, platform) pair fits its cap; exit 1 if any row is `OVER`. Same input set produces byte-identical output; suitable for CI drift detection.

---

### `skl test`

Run fixtures against compiled artefacts.

```
skl test [--skill <kebab-name>] [--all] [--mock]
```

- Reads fixtures from `tests/test-cases.yaml` per skill.
- v1 uses **structural assertions only** (per D-004 in the parent project): string-match, structural, schema. LLM-graded behavioural tests are deferred to v1.1.
- `--mock` substitutes mocked platform responses; useful in CI.
- Without `--mock`, the run is live against the configured platform endpoints (where applicable).

For Copilot Studio specifically, "live" testing emits a `manual-test-pack.md` per D-002.

---

### `skl index`

Regenerate `skills/SKILLS_INDEX.md` from the current set of skills.

```
skl index
```

Writes a deterministic markdown table - one row per skill, sorted by skill name - with columns: Name, Display, Status, Lifecycle, Platforms, Description. The file is intended to be checked in. Skills whose SKILL.md fails to parse are skipped silently; run `skl validate` to surface those errors.

Description summarisation: only the first line of the description is shown; pipes are escaped (`\|`); long lines are truncated at 120 chars with an ellipsis. Empty cells render as `-` for visual scannability.

Determinism: same input set produces byte-identical output. Re-run from CI to detect divergence from a committed index.

---

### `skl lint`

Style enforcement on SKILL.md and sidecar source files.

```
skl lint [--all] [--fix]
```

Rules enforced (severity in parentheses):

| Rule | Severity | Auto-fix | Notes |
|------|----------|----------|-------|
| `em-dash` | error | yes | Em-dash (U+2014) and en-dash (U+2013) replaced with ` - ` (space-hyphen-space). Per CLAUDE.md |
| `au-spelling` | warning | yes | US-English spellings rewritten to AU equivalents (case preserved: `Color` -> `Colour`, `COLOR` -> `COLOUR`). Wordlist is small and focused in v0.1; the lint kit in `_shared/lint/` will eventually override |
| `credentials/<vendor>` | error | no | High-signal regexes: AWS access keys (`AKIA...`), Anthropic / OpenAI / GitHub / GitLab / Slack tokens, `BEGIN PRIVATE KEY` blocks. Per [D-008](../decisions/D-008-secrets-separation.md) |
| `banned-phrase` | warning | no | `"as an AI"`, `"I cannot fulfill"` / `"I cannot fulfil"`, `"in order to"`. Per CLAUDE.md |
| `unresolved-token` | warning | no | `{{variables.X}}` references where X is not declared in `skl.variables[]`. Validate (Check 7) errors on the same condition; lint warns mid-edit |

Files scanned: `*.md`, `*.yaml`, `*.yml`, `*.txt` under each skill folder. Compiled output under the skill's top-level `platforms/` directory is **not** linted (it is derived from source). Sidecars under `skl/platforms/` **are** linted.

Auto-fix model: each fixable finding carries a `(search, replace)` substring pair applied via `str.replace(..., 1)`. Per-occurrence findings compose without overlap handling. With `--fix`, fixes are applied in place and the lint is re-run before reporting final status.

Exit codes: 0 if no error-severity findings (warnings allowed); 1 if any errors.

---

### `skl deploy`

Substitute values and copy compiled artefact to its install location.

```
skl deploy --skill <kebab-name> --platform <platform-id> [--values-file <path>] [--dry-run]
```

Order of operations:

1. Resolve tier-1 + tier-2 + tier-3 values (per D-007). Tier 3 wins.
2. Resolve secrets via the configured backend (per D-008).
3. Read the template-form artefact from `platforms/<platform>/`.
4. Substitute all `{{variables.x}}`, `{{knowledge.id}}`, `{{tools.id}}` tokens.
5. `skl lint` the substituted output; abort if a credential-shaped string is detected.
6. Copy / upload to the platform's install location.

Platform-specific install logic lives in [`compilation.md`](./compilation.md).

`--dry-run` performs steps 1-5 but does not write to the platform.

Secrets are passed to platform APIs at deploy time but **never** written to disk or to a committed artefact.

---

### `skl deprecate`

Mark a skill as deprecated.

```
skl deprecate <kebab-name> [--in-favour-of <other-kebab-name>]
```

- Sets `status: deprecated` in the skill's frontmatter.
- Writes a deprecation banner to `README.md` in the skill folder.
- If `--in-favour-of` is given, links to the replacement skill.
- Removes the skill from `skills/SKILLS_INDEX.md` on next `skl index`.

---

### `skl migrate`

Scaffold a SKILL.md draft from a legacy agent file inside the active repo.

```
skl migrate <legacy-path>
```

- **In-repo only** (per D-010). Cross-repo porting is out of scope.
- Use case in the parent project: move Casey from `copilot_studio/prompts/casey.md` to `skills/casey-case-studies/SKILL.md` with a best-effort frontmatter draft.
- Output is a draft, not a finished skill. The user must edit the result.

---

### `skl shared sync`

Fetch the shared kit (per D-011).

```
skl shared sync [--version <semver>]                       (repo-scoped)
skl shared sync --to <path> [--version <semver>]           (global)
```

Behaviour:

1. Read `shared_kit.source` and `shared_kit.version` from `skill-repo.yaml` (repo-scoped) or from CLI args (global).
2. Fetch the shared-kit repo at the specified version.
3. Write it into `./_shared/` (repo-scoped) or `<path>` (global).
4. Update `pinned_sha` in the manifest and write `_shared/.kit_version`.
5. Preserve any `_shared/local/` overlay directory untouched.

`--version` without a value picks the latest tag and updates `shared_kit.version` in the manifest.

---

### `skl values check`

Verify a values file supplies all required variables and reject secret-like keys.

```
skl values check [--values-file <path>]
```

- Without `--values-file`, checks the tier-2 values currently synced into `./.values/`.
- Rejects any key matching `*_token`, `*_secret`, `*_key`, `*_password`, `*_credential` (per D-008).
- Fails if any required variable declared in `variables[]` of an enabled skill is missing across all tiers.

---

### `skl values sync`

Sync a values profile from the sibling private values repo into `./.values/`.

```
skl values sync --from <path-or-url> [--profile <name>]
```

- `--from` can be a local path or a git URL.
- Default profile is `default`.
- `./.values/` is gitignored.
- Runs `skl values check` after sync; aborts if validation fails.

---

### `skl values schema`

Generate a JSON Schema from the union of all enabled skills' variable declarations.

```
skl values schema [--output <path>]
```

The schema is consumed by the sibling values repo's CI to prevent drift. Defaults to `./values.schema.json` (gitignored).

---

### `skl secrets`

Operate on the configured secrets backend (per D-008).

```
skl secrets get <key>
skl secrets set <key>             # prompts for value via stdin
skl secrets list                  # enumerates known keys without revealing values
```

- Backend is configured in `_shared/skill.config.yaml` `secrets.backend`. Default `keyring`.
- The `file` backend triggers a warning on every invocation and is rejected in CI (exit 3).

---

## See also

- [`manifest.md`](./manifest.md) - the `skill-repo.yaml` schema referenced throughout.
- [`compilation.md`](./compilation.md) - per-platform compiler contracts.
- [`values-and-secrets.md`](./values-and-secrets.md) - deep-dive on D-007 + D-008.
- Parent project `ai-skills-lib/analysis/03_convenience_scripts_spec.md` - the original full spec.
