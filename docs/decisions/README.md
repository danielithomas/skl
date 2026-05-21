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
| [SKL-004](./SKL-004-master-skill-md-posture.md) | Master SKILL.md posture: Anthropic Skills base + `skl:` extensions, with progressive sidecars | Frontmatter shape, folder layout (`skl/platforms/<id>.yaml`), validator cross-checks, scaffolding template |
| [SKL-005](./SKL-005-defer-handoff-modelling.md) | Defer multi-agent / handoff modelling to v0.2+ | `_shared/schemas/skill.frontmatter.schema.json` omits `handoffs`; authors use platform-native sidecar fields in v0.1 |
| [SKL-006](./SKL-006-strip-skl-block-on-skills-native-compile.md) | Strip `skl:` frontmatter on Skills-native compile; emit top-line provenance comment across all compilers | Skills-native compilers remove `skl:` from compiled SKILL.md; every compiler emits `# Compiled by skl <version> from <source> on <date>` |
| [SKL-007](./SKL-007-vscode-emit-skill-and-custom-agent.md) | VS Code emits Skill + Custom Agent variants when sidecar present; never emits `.chatmode.md` | Two-stage VS Code compiler; `emit_skill: false` opt-out in `skl/platforms/vscode.yaml`; body content rules deferred to Q-009 |
| [SKL-008](./SKL-008-persona-defaults-skills-format-refresh.md) | Per-target persona defaults refreshed for Skills-format era; supersedes D-006 table for `skl`'s purposes | claude-code / claude-cowork / ms-cowork strip; VS Code splits (Skill strip, Custom Agent surface); per-skill override deferred to v0.2 |
| [SKL-009](./SKL-009-m365-schema-versioning.md) | Per-skill M365 `schema_version` pin in sidecar; multi-version kit; schema iteration is a kit event, not an `skl` event | M365 sidecar requires `schema_version`; bundled output schemas at `_shared/schemas/platforms/m365/declarative-agent-manifest-<v>.json` + `index.json`; `skl init` scaffolds pin from kit default |
| [SKL-010](./SKL-010-compat-guard-edge-cases.md) | Compatibility-guard edge cases: `SKL_IGNORE_COMPAT` env var, fail-fast on parse failure, skip list unchanged | Closes SKL-003's deferred edge cases; implementation deltas land in a follow-up code PR |

## Parent decisions referenced by this spec

These decisions live in the parent project. They are not mirrored here because they primarily constrain authoring, but the spec references them where the toolkit must respect them at build time.

| ID | Title | Where `skl` references it |
|----|-------|---------------------------|
| D-001 | Compiled `platforms/` artefacts are committed | `cli.md` §`skl compile`; `values-and-secrets.md` (substitution-at-deploy-time preserves D-001) |
| D-002 | Copilot Studio "live" testing emits a manual-test-pack | `cli.md` §`skl test`; `compilation.md` §`copilot-studio` |
| D-004 | LLM-graded behavioural tests deferred to v1.1; structural assertions only in v1 | `cli.md` §`skl test` |
| D-006 | Persona surfacing mechanism (`personas.surface_in`), kebab-prefix-matches-nickname rule | `compilation.md` per-platform table. **Note**: D-006's specific per-target defaults table is superseded by [SKL-008](./SKL-008-persona-defaults-skills-format-refresh.md) for `skl`'s purposes (refresh for the Skills-format era). The mechanism and kebab rule carry forward unchanged |

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
