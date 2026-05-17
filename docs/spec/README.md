# `skl` Specification

This directory is the authoritative specification for `skl`'s external surface and behaviour. The implementation must match the spec, not the other way around.

## Documents

| File | What it covers |
|------|----------------|
| [`cli.md`](./cli.md) | Every CLI verb, its arguments, exit codes, and global behaviour |
| [`manifest.md`](./manifest.md) | The `skill-repo.yaml` manifest schema and validation rules |
| [`infrastructure.md`](./infrastructure.md) | Installation model, repo discovery, versioning, compatibility policy |
| [`values-and-secrets.md`](./values-and-secrets.md) | Three-tier values model (D-007), pluggable secrets backend (D-008), deploy-time substitution |
| [`compilation.md`](./compilation.md) | Per-platform compilers, output contracts, validators, character budgets |

## Scope boundaries

- **In scope**: the `skl` CLI binary and its behaviour.
- **Out of scope**: the content of a `SKILL.md` file (that is the SKILL.md spec, which lives in the parent project: `ai-skills-lib/analysis/02_portable_skill_specification.md`). `skl` *consumes* that spec; it does not own it.
- **Out of scope**: the content of the shared kit (`_shared/skill.config.yaml`, personas, templates, schemas). That lives in `ai-skills-shared` (planned). `skl` *fetches* it; it does not own it.
- **Out of scope**: tenant values, customer-specific configuration, secrets material. Those live in private repos / secrets backends per D-007 and D-008.

## Maturity

Pre-v0.1. The spec is settled enough to author from; implementation has not started.

## See also

- `docs/decisions/` for the decisions that constrain this spec.
- `ai-skills-lib/analysis/` for the full design history.
