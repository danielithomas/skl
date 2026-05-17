# `skl` Decisions

These are the decisions that constrain `skl`'s behaviour. Each file is self-contained for readers working in this repo, but the authoritative project-wide record lives in [`ai-skills-lib/analysis/06_decision_log.md`](https://github.com/danielithomas/ai-skills-lib/blob/main/analysis/06_decision_log.md).

The decision IDs (D-007, D-008, etc.) match the parent project's numbering. Decisions D-001 to D-006 are about skill content and authoring conventions; they constrain SKILL.md authors, not the toolkit, so they live in the parent project only.

| ID | Title | What it constrains in `skl` |
|----|-------|----------------------------|
| [D-007](./D-007-three-tier-values.md) | Three-tier values model with sibling private values repo | `skl deploy`, `skl values *`, the template-form nature of `platforms/` artefacts |
| [D-008](./D-008-secrets-separation.md) | Config and secrets are separate; pluggable secrets backend | `skl secrets *`, `skl lint` (credential detection), `skl values check` (reject secret-like keys) |
| [D-009](./D-009-multi-repo-architecture.md) | Multi-repo skill architecture | `skl init`, repo discovery, `skill-repo.yaml` manifest |
| [D-010](./D-010-toolkit-identity.md) | Toolkit extracted to this repo; CLI binary named `skl` | The existence and identity of this repo |
| [D-011](./D-011-shared-kit-fetched.md) | Shared kit fetched via `skl shared sync` from `ai-skills-shared` | `skl shared sync`, `skl validate` (drift detection), `_shared/` integration |

## Process

A change to `skl`'s external surface (CLI verbs, manifest schema, compiler output contract, shared-kit integration) should land as a decision document here before code. The bar is intentionally low: a one-page file with Question, Decision, and Rationale is enough. Internal refactors do not need a decision.

When a decision is taken upstream in the parent project and affects `skl`, mirror it here with the same ID and a pointer back to the parent record.

## Pending

| ID | Question | Why open |
|----|----------|----------|
| P-009 | Future-state: should `skl deploy` emit packages consumable by `skillctl install` (or successor distribution tools)? | Tracked since the P-008 closure (`skillctl` distinct from `skl`). Worth revisiting once `skl` v0.1 ships and the deploy output is stable |
