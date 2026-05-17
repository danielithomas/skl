# `skill-repo.yaml` manifest

Every skill-host repo declares itself with a `skill-repo.yaml` at the root. It is the source of truth for `skl` about the repo. Distilled from D7 §5.

---

## Schema (v1)

```yaml
schema_version: 1                          # bumped on breaking changes to this file
name: ea-assessment                        # kebab; matches the repo name by convention
description: ISO-grounded Enterprise Architecture assessment skill library
visibility: internal                       # public | internal | restricted (closes P-007)
custodian: dan@theenquiringmind.com        # who owns this repo
skl_version: ">=1.0,<2.0"                  # required skl semver range
shared_kit:
  source: github.com/<org>/ai-skills-shared
  version: "1.4.2"                         # exact version pinned
  pinned_sha: 7c3f9a2                      # auto-written by `skl shared sync`
enabled_platforms:                         # subset of platforms this repo targets
  - claude-code
  - copilot-studio
  - m365
  - vscode
cross_repo_dependencies: []
  # - name: ai-skills-lib
  #   source: github.com/<org>/ai-skills-lib
  #   pinned_sha: a1b2c3d
  #   used_for: MAS sub-agents
defaults:
  output_language: en-AU                   # surfaced into compiled skills via shared kit
```

The secrets backend (per D-008) is configured in `_shared/skill.config.yaml`, not here. Per-machine overrides belong in `_shared/local/skill.config.yaml`.

---

## Field reference

### Required

| Field | Type | Meaning |
|-------|------|---------|
| `schema_version` | int | Currently `1`. Bumped on breaking changes to this schema |
| `name` | kebab string | Logical repo identifier. Conventionally matches the GitHub repo name |
| `visibility` | enum | One of `public`, `internal`, `restricted`. Drives where the repo can be hosted and who can read it |
| `skl_version` | semver range | The range of `skl` versions this repo is known to work with. `skl` refuses to run if outside the range (exit 4) |
| `shared_kit.source` | string | Git URL or `github.com/<org>/<repo>` shorthand for the shared-kit repo |
| `shared_kit.version` | semver or `"latest"` | Pinned shared-kit version. The literal string `"latest"` is a sentinel that `skl shared sync` resolves to the highest semver tag in the source repo and rewrites in place. See [The `"latest"` sentinel](#the-latest-sentinel) below |
| `enabled_platforms` | list | Subset of `[copilot-studio, m365, ms-cowork, claude-code, claude-cowork, vscode]` |

### Optional

| Field | Type | Meaning |
|-------|------|---------|
| `description` | string | Free text. Surfaced in `skl --help` for the active repo |
| `custodian` | string | Email or handle of the owner. Surfaced in `--help` and error messages |
| `shared_kit.pinned_sha` | string | Resolved commit SHA. Auto-written by `skl shared sync`; do not hand-edit |
| `cross_repo_dependencies[]` | list of objects | See below |
| `defaults` | map | Repo-wide defaults inherited by skills. Currently only `output_language` |

### `cross_repo_dependencies[]`

When a skill in this repo references a skill in another repo (e.g. for documentation, or in v2 for MAS composition), the cross-repo dependency is declared here. `skl validate` checks the SHA resolves; `skl.lock` records the actual resolved SHA.

```yaml
cross_repo_dependencies:
  - name: ai-skills-lib
    source: github.com/danielithomas/ai-skills-lib
    pinned_sha: a1b2c3d4e5f6
    used_for: "MAS sub-agent references"
```

---

## Validation rules

`skl validate` enforces:

1. `schema_version` is within the range `skl` understands.
2. `name` is kebab-case and matches `^[a-z][a-z0-9-]{0,62}$`.
3. `visibility` is one of `public | internal | restricted`.
4. `skl_version` parses as a valid semver range and matches the installed `skl`.
5. `shared_kit.source` is fetchable; `shared_kit.version` is an available tag.
6. `enabled_platforms` is a subset of known platforms (see [`compilation.md`](./compilation.md)).
7. `cross_repo_dependencies[]` each resolve to fetchable repos at the pinned ref.

---

## Default values

If absent, the following defaults apply:

| Field | Default |
|-------|---------|
| `description` | `(none)` |
| `custodian` | `(none)` |
| `cross_repo_dependencies` | `[]` |
| `defaults.output_language` | `en-AU` |

---

## The `"latest"` sentinel

`shared_kit.version` accepts the literal string `"latest"` in addition to a real semver. `skl init` writes `version: "latest"` by default so a freshly scaffolded manifest does not require the user to know which kit tags exist; the first `skl shared sync` resolves the sentinel against the source's git tags (highest semver wins) and rewrites the manifest with the concrete version plus the resolved `pinned_sha`.

A manifest with `version: "latest"` is not yet pinned. Validate / compile / deploy workflows that assume a pinned manifest should treat the sentinel as a pre-sync state and either run `skl shared sync` first or fail with a clear message.

---

## Visibility and trust

| Visibility | Implication |
|------------|-------------|
| `public` | The repo can be hosted publicly. `skl validate` enforces that no values file or compiled artefact contains commercially-sensitive strings or credential-shaped material |
| `internal` | The repo holds practice-internal content. Hosted on the firm's own infrastructure. Default for most skill-host repos |
| `restricted` | The repo contains commercially-sensitive content (customer data, paywalled framework excerpts, etc.). Must be hosted in a private repo with explicit access control. `skl validate` enforces additional checks before deploy |

This closes P-007 in the parent project.

---

## See also

- [`infrastructure.md`](./infrastructure.md) - how `skl` discovers and uses this file.
- [`cli.md`](./cli.md) - which commands read which fields.
- D-009 in `docs/decisions/` - the architectural decision this manifest enacts.
