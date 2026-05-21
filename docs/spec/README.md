# `skl` Specification

This directory is the authoritative specification for `skl`'s external surface and behaviour. The implementation must match the spec, not the other way around.

## Documents

| File | What it covers |
|------|----------------|
| [`cli.md`](./cli.md) | Every CLI verb, its arguments, exit codes, and global behaviour |
| [`manifest.md`](./manifest.md) | The `skill-repo.yaml` manifest schema and validation rules |
| [`skill-md.md`](./skill-md.md) | SKILL.md authoring contract: frontmatter shape, body sections, sidecar layout, scaffolding |
| [`infrastructure.md`](./infrastructure.md) | Installation model, repo discovery, versioning, compatibility policy |
| [`values-and-secrets.md`](./values-and-secrets.md) | Three-tier values model (D-007), pluggable secrets backend (D-008), deploy-time substitution |
| [`compilation.md`](./compilation.md) | Per-platform compilers, output contracts, validators, character budgets |

## Scope boundaries

- **In scope**: the `skl` CLI binary and its behaviour.
- **In scope**: the SKILL.md contract `skl` consumes (see `skill-md.md`). The parent project (`ai-skills-lib/analysis/02_portable_skill_specification.md`) carried earlier drafts of this contract; SKL-004 through SKL-009 in this repo are the current authoritative source for `skl`'s consumption.
- **Out of scope**: the content of the shared kit (`_shared/skill.config.yaml`, personas, templates, schemas). That lives in `ai-skills-shared` (planned). `skl` *fetches* it; it does not own it.
- **Out of scope**: tenant values, customer-specific configuration, secrets material. Those live in private repos / secrets backends per D-007 and D-008.

## Maturity

v0.1 in progress. The spec is settled; Stage 1 (authoring foundation) is implemented; Stages 2-7 (compilers, deploy, secrets, test/migrate/deprecate) remain. See [`docs/plan.md`](../plan.md) for the rollout.

## See also

- `docs/decisions/` for the decisions that constrain this spec.
- `ai-skills-lib/analysis/` for the full design history.
