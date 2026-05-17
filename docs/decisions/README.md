# `skl` Decisions

These are the decisions that constrain `skl`'s behaviour. Each file is self-contained for readers working in this repo. There are two prefixes:

- **`D-NNN`** - decisions mirrored from the parent project (`ai-skills-lib`). Same ID as the parent's authoritative log at [`ai-skills-lib/analysis/06_decision_log.md`](https://github.com/danielithomas/ai-skills-lib/blob/main/analysis/06_decision_log.md). Decisions D-001..D-006 are not mirrored here (they constrain SKILL.md authors more than the toolkit) - see "Parent decisions referenced by this spec" below.
- **`SKL-NNN`** - decisions specific to this repo (the `skl` toolkit itself). Numbered locally, starting at SKL-001. Used for choices that emerge during implementation - flag semantics, CLI guard behaviour, internal architecture - that do not need to cross-reference the parent project.

The two prefixes are deliberately separate so future numbering does not collide if the parent project adds further `D-NNN` decisions.

## Mirrored from the parent project

| ID | Title | What it constrains in `skl` |
|----|-------|----------------------------|
| [D-007](./D-007-three-tier-values.md) | Three-tier values model with sibling private values repo | `skl deploy`, `skl values *`, the template-form nature of `platforms/` artefacts |
| [D-008](./D-008-secrets-separation.md) | Config and secrets are separate; pluggable secrets backend | `skl secrets *`, `skl lint` (credential detection), `skl values check` (reject secret-like keys) |
| [D-009](./D-009-multi-repo-architecture.md) | Multi-repo skill architecture | `skl init`, repo discovery, `skill-repo.yaml` manifest |
| [D-010](./D-010-toolkit-identity.md) | Toolkit extracted to this repo; CLI binary named `skl` | The existence and identity of this repo |
| [D-011](./D-011-shared-kit-fetched.md) | Shared kit fetched via `skl shared sync` from `ai-skills-shared` | `skl shared sync`, `skl validate` (drift detection), `_shared/` integration |

## Local to `skl`

| ID | Title | What it constrains in `skl` |
|----|-------|----------------------------|
| [SKL-001](./SKL-001-drift-is-warning.md) | Shared-kit drift is a warning, not an error in `skl validate` | `skl validate` exit-code mapping; `_check_shared_kit_drift` accumulates warnings only |
| [SKL-002](./SKL-002-unimplemented-flags-error.md) | Unimplemented CLI flags raise `NotImplementedError` | Every documented-but-unbuilt flag must error rather than no-op |
| [SKL-003](./SKL-003-global-compatibility-guard.md) | Global `skl_version` compatibility guard at CLI entry | `skl.cli.main` runs the check before every non-exempt subcommand; skip list is `{init, validate}` |

## Parent decisions referenced by this spec

These decisions live in the parent project. They are not mirrored here because they primarily constrain authoring, but the spec references them where the toolkit must respect them at build time.

| ID | Title | Where `skl` references it |
|----|-------|---------------------------|
| D-001 | Compiled `platforms/` artefacts are committed | `cli.md` §`skl compile`; `values-and-secrets.md` (substitution-at-deploy-time preserves D-001) |
| D-002 | Copilot Studio "live" testing emits a manual-test-pack | `cli.md` §`skl test`; `compilation.md` §`copilot-studio` |
| D-004 | LLM-graded behavioural tests deferred to v1.1; structural assertions only in v1 | `cli.md` §`skl test` |
| D-006 | Persona surfacing defaults are platform-specific, driven by `personas.surface_in` | `compilation.md` per-platform table |

Full text in [`ai-skills-lib/analysis/06_decision_log.md`](https://github.com/danielithomas/ai-skills-lib/blob/main/analysis/06_decision_log.md).

## Process

Decisions and the open questions that lead to them are tracked as a pair:

- **Open questions** live in [`docs/open-questions.md`](../open-questions.md) with `Q-NNN` IDs. Add an entry when a question is raised that is worth recording the answer to - typically during PR review.
- **Decisions** live here, one file per decision, named `SKL-NNN-<short-slug>.md` (or `D-NNN-...` for parent-mirrored). Each one names the question it resolves; the matching question gets a strikethrough heading and a "Resolved by" link.
- The bar for a decision file is low: one page, with Question / Decision / Rationale / What this constrains. Internal refactors do not need a decision.

When a decision is taken upstream in the parent project and affects `skl`, mirror it here with the same `D-NNN` ID and a pointer back to the parent record.

## Pending parent-project questions

| ID | Question | Why open |
|----|----------|----------|
| P-009 | Future-state: should `skl deploy` emit packages consumable by `skillctl install` (or successor distribution tools)? | Tracked since the P-008 closure (`skillctl` distinct from `skl`). Worth revisiting once `skl` v0.1 ships and the deploy output is stable |

(Local `skl` questions live in [`open-questions.md`](../open-questions.md), not here.)
