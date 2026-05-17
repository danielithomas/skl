# D-009 - Multi-repo skill architecture

| Field | Value |
|-------|-------|
| **ID** | D-009 |
| **Date** | 17 May 2026 (decided in parent project) |
| **Status** | Final |
| **Owner** | Daniel Thomas |
| **Parent record** | [`ai-skills-lib/analysis/06_decision_log.md` §D-009](https://github.com/danielithomas/ai-skills-lib/blob/main/analysis/06_decision_log.md) |

## Question

Should every skill live inside a single repo (`ai-skills-lib`), or should the architecture support multiple skill-host repos sharing common tooling and configuration?

## Decision

Multi-repo. Four repo classes:

| Class | Examples | Purpose |
|-------|----------|---------|
| **Skill-host repos** | `ai-skills-lib`, `ea-assessment`, future libs | Hold one or more skills. Declare themselves via `skill-repo.yaml` |
| **Tooling repo** | `skl` (this repo) | Holds the CLI |
| **Shared-kit repo** | `ai-skills-shared` (planned) | Holds canonical `_shared/` content. Fetched into skill-host repos via `skl shared sync` (per D-011) |
| **Values repo** | `<company>-skill-values` (private) | Tier-2 values per D-007 |

`ai-skills-lib` is one skill-host repo among several; its existing migration sequence is unchanged. The EA Assessment skill (~400 ISO-grounded EA rules) lives in its own skill-host repo, authored natively - no port / sync into `ai-skills-lib`.

`visibility: public | internal | restricted` is a manifest field; restricted skills live in private repos by default. This closes P-007 in the parent project.

Per-repo overlays in `_shared/local/skill.config.yaml` let specialist libraries extend the allowed-frameworks list without affecting other repos.

## What this constrains in `skl`

- **Repo discovery**: `skl` walks up from `$PWD` looking for `skill-repo.yaml`. The first match is the active skill-host repo. Most commands fail outside one.
- **`skl init`** has two forms: global (scaffold a new skill-host repo) and repo-scoped (scaffold a new skill inside the active repo).
- **`skl validate`** checks `skill-repo.yaml` against the manifest schema in [`docs/spec/manifest.md`](../spec/manifest.md).
- **Cross-repo composition** is in scope only as identity references in v1 (`<repo>/<skill-kebab-name>`) with a `skl.lock` lock file. Cross-repo MAS composition is deferred to v2.
- **Visibility checks**: `skl validate` and `skl deploy` apply additional checks for `restricted` repos (e.g. no public-PyPI distribution, additional credential-pattern checks).

## Rationale

Specialist libraries (~400 rules for EA, similar volumes plausible for AWS Well-Architected, NIST CSF, etc.) need their own custodianship cadence and trust boundary. Folding them into `ai-skills-lib` would drown the lib, conflate custodianship, and create a port-sync question every time the source is edited.

The multi-repo pattern reuses precedent already set by D-007's sibling values repo. It closes P-007 (privacy tiers) as a side effect: restricted skills live in private repos, with no manifest gymnastics needed.

The cost is real (more moving parts, shared-kit drift discipline) but bounded. D-010 contains the tooling cost; D-011 contains the shared-kit cost.

## See also

- [`docs/spec/infrastructure.md`](../spec/infrastructure.md) - how `skl` operates across repos.
- [`docs/spec/manifest.md`](../spec/manifest.md) - the `skill-repo.yaml` schema this decision enacts.
- [`docs/decisions/D-010-toolkit-identity.md`](./D-010-toolkit-identity.md) - why this repo exists.
- [`docs/decisions/D-011-shared-kit-fetched.md`](./D-011-shared-kit-fetched.md) - the shared-kit fetch model.
- Parent project [`ai-skills-lib/analysis/07_multi_repo_skill_architecture.md`](https://github.com/danielithomas/ai-skills-lib/blob/main/analysis/07_multi_repo_skill_architecture.md) - the full architecture document.
