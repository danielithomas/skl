# D-011 - Shared kit fetched on init/update via the CLI

| Field | Value |
|-------|-------|
| **ID** | D-011 |
| **Date** | 17 May 2026 (decided in parent project) |
| **Status** | Final |
| **Owner** | Daniel Thomas |
| **Parent record** | [`ai-skills-lib/analysis/06_decision_log.md` §D-011](https://github.com/danielithomas/ai-skills-lib/blob/main/analysis/06_decision_log.md) |

## Question

How should `_shared/` content (style rules, personas, scaffold templates, schemas) be distributed across skill-host repos?

## Decision

Fetched via `skl shared sync`. Each skill-host repo carries a pinned, committed local copy of `_shared/`.

1. **Source of truth**: a dedicated shared-kit repo (`ai-skills-shared`, planned).
2. **Distribution**: `skl shared sync` reads `shared_kit.source` and `shared_kit.version` from `skill-repo.yaml`, fetches the kit at that version, writes it into `./_shared/`, updates `pinned_sha`, and writes `_shared/.kit_version`.
3. **Committed, not gitignored**. A clone-and-run workflow must function offline (consistent with D-001's posture on platform artefacts).
4. **Upgrade**: `skl shared sync --version X.Y.Z` to move; `skl shared sync` with no version takes the latest tag and updates `shared_kit.version` in the manifest.
5. **Local overrides**: `_shared/local/` may overlay any kit file. `skl` applies overrides last in the resolution order; the kit copy itself is read-only as far as `skl` is concerned.
6. **Drift detection**: `skl validate` warns if `_shared/.kit_version` does not match `shared_kit.version` in the manifest, listing divergent files.

## What this constrains in `skl`

- **`skl shared sync`** is the only sanctioned way to update `_shared/`. Users do not edit kit files directly; they edit `_shared/local/` overrides.
- **`skl validate`** runs a shared-kit drift check on every invocation.
- **`skl init`** (global form) runs `skl shared sync` internally so a newly-scaffolded repo has a working kit immediately.
- **Kit consumption**: `skl` reads `_shared/skill.config.yaml` and `_shared/schemas/*.json` as the source of truth for style rules, schemas and templates. It does NOT fetch them at runtime from a remote.
- **Resolution order at runtime**: when a file exists in both `_shared/` and `_shared/local/`, the local copy wins.

## Rationale

Live consumption (always-fetch-at-runtime) requires network / auth and breaks offline use. Submodules couple repos tightly and complicate per-repo overrides. Vendored divergence (each repo holds its own kit and edits it freely) invites drift across the fleet.

Fetch-on-update with a pinned committed copy gives explicit, versioned upgrades; supports per-repo overlays without forking the kit; keeps the kit usable offline; and produces clear drift diagnostics. The cost is one extra `skl shared sync` step on initial setup and on upgrade.

## See also

- [`docs/spec/infrastructure.md`](../spec/infrastructure.md) §The shared kit.
- [`docs/spec/cli.md`](../spec/cli.md) §`skl shared sync`.
- [`docs/decisions/D-009-multi-repo-architecture.md`](./D-009-multi-repo-architecture.md) - the multi-repo context.
