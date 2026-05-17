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

**Repo-scoped form** - `skl init <skill-kebab-name>`

Creates `skills/<skill-kebab-name>/` populated from the shared kit's standalone-skill template. Fails with exit 3 if `./_shared/` is absent (run `skl shared sync` first). The user fills in frontmatter, body, knowledge contracts, and fixtures.

---

### `skl validate`

Validate frontmatter, body, knowledge contracts, references, and shared-kit drift.

```
skl validate [--skill <kebab-name>] [--all]
```

Checks performed:
1. **Manifest** - `skill-repo.yaml` matches the documented schema.
2. **Frontmatter** - every SKILL.md's YAML frontmatter matches the schema in `_shared/schemas/skill.frontmatter.schema.json`.
3. **Body** - canonical section order is present and complete; section anchors compilers depend on are found.
4. **Knowledge contracts** - every contract referenced in frontmatter exists; every contract's referenced files exist; cross-references resolve.
5. **Cross-repo dependencies** - entries in `cross_repo_dependencies[]` resolve at the pinned SHA.
6. **Shared-kit drift** - `_shared/.kit_version` matches `shared_kit.version` in the manifest; warns on divergent files.
7. **Values declarations** - every `variables[]` entry in a SKILL.md has either a declared default or is supplied by tier-1 / tier-2 / tier-3 values.
8. **Compatibility** - the installed `skl` version is within the manifest's `skl_version` range.

Exit codes: 0 (pass), 1 (validation failure), 4 (compatibility failure).

---

### `skl compile`

Compile each SKILL.md into platform-specific artefacts written under the skill's `platforms/` directory.

```
skl compile [--skill <kebab-name>] [--platform <platform-id>] [--all]
```

- Runs `skl validate` first; aborts on errors unless `--force` is passed.
- For each `enabled_platforms` entry in the manifest, the corresponding compiler in `compilation.md` runs.
- Artefacts are written in **template form** (per D-007): `{{variables.x}}` and `{{knowledge.id}}` tokens remain unresolved. Substitution happens at deploy time, not compile time.
- The output is committed to the repo (D-001), giving non-developer colleagues a directly consumable build.

---

### `skl budget`

Report character usage versus per-platform budget.

```
skl budget [--skill <kebab-name>] [--all]
```

Currently enforced budgets:

| Platform | Budget | Notes |
|----------|--------|-------|
| Copilot Studio | 8,000 chars | Hard limit imposed by the platform |
| M365 Copilot | 8,000 chars | Same as above |
| Claude Code | None | But warn if > 50,000 |
| Other platforms | None | Reserved |

Exit 1 if any skill exceeds a hard budget. The character counter is the same one used historically in `utils/character_counter.py` of the parent project.

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

Lists every skill by `display_name`, `name`, status, lifecycle phase, and a one-line summary. Grouped by lifecycle phase (e.g. `business_development`, `bid`, `delivery_run`).

---

### `skl lint`

Style enforcement.

```
skl lint [--skill <kebab-name>] [--all] [--fix]
```

Rules enforced:

- **No em-dashes (`—`) or en-dashes (`–`).** Replace with ` - ` (hyphen with surrounding spaces).
- **Australian English spellings**: `organise` / `realise` / `colour` / `catalogue` / `optimisation`. Configurable via `_shared/skill.config.yaml`.
- **No "as an AI", "I cannot fulfill", "in order to"** in any output text.
- **Unresolved tokens**: any `{{...}}` remaining in compiled output after deploy-time substitution is an error.
- **Credential-shaped strings** in compiled artefacts: high-entropy strings, recognised prefixes (`eyJ...`, `xoxb-...`, `sk-...`, `ghp_...`). Per D-008.
- **Persona / kebab-prefix consistency**: when `persona.nickname` or `persona.role` is set, the kebab `name`'s first segment must match it (lowercased). Per D-006.

`--fix` applies auto-fixable rules in place; the rest are reported.

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
