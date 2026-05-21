# Open questions

Live questions and decisions-in-flight for `skl`. Each entry stays here forever - the audit trail of "what we discussed and why we picked X" is more useful than a clean slate. When a question lands a decision, its heading gets struck through and a "Resolved by" link points at the [decision file](decisions/).

## Conventions

- IDs are `Q-NNN`, local to this repo, numbered in order they were raised.
- Resolved questions are kept under "Resolved", in numeric order, with strikethrough on the heading and a link to the deciding [SKL-NNN](decisions/) record.
- A decision can resolve several questions; an open question can spawn several decisions and stay open until all are settled.
- Cross-link liberally between this file, decision files, and the PR or conversation that raised the question.

---

## Open

## Resolved

### ~~Q-001 - Drift severity in `skl validate`: warning or error?~~

The first `skl validate` PR treated `_shared/` drift relative to the manifest as a warning, not an error. Question was: should drift cause validate to fail (exit 1), or just warn?

Resolved by [SKL-001](decisions/SKL-001-drift-is-warning.md): drift is a warning. The spec language is "warns on divergent files"; drift is recoverable; the user fixes it on the next `skl shared sync`.

### ~~Q-002 - `skl validate --skill` / `--all`: silent no-op or "not yet implemented"?~~

Flags were accepted on the CLI (matching the spec) but no-oped with a stderr note. Question was: keep the silent no-op, or raise "not yet implemented"?

Resolved by [SKL-002](decisions/SKL-002-unimplemented-flags-error.md): unimplemented flags raise `NotImplementedError`, matching the convention used by unimplemented verbs.

### ~~Q-003 - Global `skl_version` compatibility guard: per-verb or every invocation?~~

`docs/spec/infrastructure.md` says `skl` should refuse to run if the installed version is outside the manifest's range, on every invocation. Initial validate PR scoped this to `skl validate` only. Question was: promote to a global CLI entry-point check?

Resolved by [SKL-003](decisions/SKL-003-global-compatibility-guard.md): yes, the guard fires at the top-level group callback for every subcommand inside a skill-host repo, with a small skip list (`init`, `validate`). Edge cases tracked separately as [Q-004](#q-004---global-skl_version-compatibility-guard-edge-cases).

### ~~Q-004 - Global `skl_version` compatibility guard: edge cases~~

Four edge cases were deferred from SKL-003: an escape hatch for emergency cases, the unparseable-manifest behaviour, the `--version` / `--help` exemption, and possible skip-list extensions for `deprecate` / `shared sync`.

Resolved by [SKL-010](decisions/SKL-010-compat-guard-edge-cases.md): `SKL_IGNORE_COMPAT=1` env var as escape hatch (loud bypass; no flag form in v0.x); unparseable manifest now fails fast at the guard with a message pointing at `skl validate` (supersedes silent skip); `--version` / `--help` exemption documented as relying on click's eager-option exit; skip list stays at `{init, validate}` - the escape hatch covers the candidate cases. Implementation deltas land in a follow-up code PR.

### ~~Q-012 - M365 declarative-agent schema versioning: how do we track Microsoft's iteration?~~

The M365 declarative-agent manifest moved v1.3 -> v1.7 in ~6 months. Question was how `skl` tracks Microsoft's iteration cadence: per-skill pin vs always-latest, single vs multi-version kit, and whether each Microsoft release should trigger an `skl` version bump.

Resolved by [SKL-009](decisions/SKL-009-m365-schema-versioning.md): per-skill `schema_version` pin in `skl/platforms/m365.yaml` is mandatory and authoritative; the kit ships multiple supported schema versions side by side under `_shared/schemas/platforms/m365/` with an `index.json` declaring default / supported / deprecated; M365 schema iteration is a kit-level event delivered via `skl shared sync`, not an `skl` version bump. `skl validate` errors on missing pinned version, soft-warns on older-than-default, strong-warns on deprecated. `compilation.md` and `infrastructure.md` updated.

### ~~Q-009 - Persona stripping defaults per target, in light of Skills format having no persona field~~

The Anthropic Skills format does not model persona as a first-class field; the convention is to keep skills capability-focused. D-006 set per-platform persona defaults *before* Skills became the cross-platform standard, treating claude-code and claude-cowork as persona-surfacing. The analysis (§7.3, §8.1) reframed this: on Claude-family surfaces Claude is already the persona, so Skills-native targets should strip Identity by default.

Resolved by [SKL-008](decisions/SKL-008-persona-defaults-skills-format-refresh.md): refreshed per-target table - claude-code, claude-cowork, ms-cowork strip (flipped from D-006); copilot-studio surfaces; m365 strips; VS Code splits into Skill variant (strip) and Custom Agent variant (surface) per SKL-007. Per-skill override (`skl.persona.surface_for` / `strip_for`) deferred to v0.2 - repo-level `personas.surface_in` already exists; no authored evidence yet for a per-skill mechanism. `docs/spec/compilation.md` table updated.

### ~~Q-008 - VS Code: Agent Skill, Custom Agent, or both?~~

VS Code natively consumes both Anthropic Agent Skills (`.github/skills/`, `.claude/skills/`) and Custom Agents (`.github/agents/<name>.agent.md`). [SKL-004](decisions/SKL-004-master-skill-md-posture.md) established that the opt-in signal for Custom Agent emission is the presence of `skl/platforms/vscode.yaml`. Open sub-questions: emit both variants or Custom Agent only when sidecar present; should `.chatmode.md` ever be emitted; do body content rules live here or with Q-009.

Resolved by [SKL-007](decisions/SKL-007-vscode-emit-skill-and-custom-agent.md): sidecar present -> emit both variants by default, opt out of Skill emission via `emit_skill: false` in the sidecar. Never emit `.chatmode.md`. Body content rules deferred to Q-009; this decision covers which files get emitted and how the Custom Agent frontmatter composes.

### ~~Q-007 - Compiled artefacts for Skills-native targets: strip `skl:` block or pass through?~~

For `claude-code`, `claude-cowork`, `ms-cowork` (and any future Skills-consuming surface), compile is essentially a copy. Question was: do we strip the `skl:` frontmatter block from the compiled SKILL.md, or pass it through?

Resolved by [SKL-006](decisions/SKL-006-strip-skl-block-on-skills-native-compile.md): strip the entire `skl:` block. Reverse-trip footgun (compiled artefact copied back into a skill-host repo) and information-hygiene reasons outweigh the source/artefact-symmetry argument for pass-through. Provenance preserved via a top-line `# Compiled by skl <version> from <source> on <date>` comment - a convention applied across all compilers, not only Skills-native.

### ~~Q-005 - Master SKILL.md posture: Anthropic-Skills base with `skl:` extensions, or fully bespoke superset?~~

[`analysis/skills-spec.md`](analysis/skills-spec.md) §7 lands on **Anthropic Skills format as the base layer + `skl:` namespaced extensions for the superset surface**. The reasoning: five of six target platforms already accept Anthropic SKILL.md directly, so taking the open standard as the base means the four Skills-native targets compile for free.

Alternatives that were on the table:
- Fully bespoke `skl` schema (top-level fields for everything; `name` / `description` happen to coincide with Anthropic's). Cleaner internal model, loses the "valid Anthropic Skill out of the box" property.
- Anthropic-Skills-only (no `skl:` extensions). Forces all non-Skills targets to derive everything from `description` + body. Pure but loses the binding declarations the non-Skills compilers need.

Resolved by [SKL-004](decisions/SKL-004-master-skill-md-posture.md): Anthropic Skills base with `skl:` extensions, plus a progressive-sidecar layout (`skl/platforms/<id>.yaml`) so per-platform bindings and overrides do not bloat the master frontmatter. Knowledge / tool IDs live in SKILL.md; bindings live in the per-platform sidecars.

### ~~Q-006 - Frontmatter namespacing for `skl`-added fields~~

If we accept the §7.3 proposal in [`analysis/skills-spec.md`](analysis/skills-spec.md), `skl` adds metadata to the SKILL.md frontmatter under a single `skl:` top-level key. Two questions followed:

- Is `skl:` the right namespace? Alternatives: `x-skl:`, separate top-level keys with `skl-` prefix (`skl-knowledge:`, `skl-tools:`), or a sibling `skill.config.yaml` file alongside SKILL.md.
- Should per-platform sub-blocks (`m365:`, `vscode:`, ...) live under `skl:` (`skl.m365`) or top-level (`m365:`)?

Resolved by [SKL-004](decisions/SKL-004-master-skill-md-posture.md): `skl:` is the single inline top-level namespace; per-platform content does not live inline at either location and instead lives in sidecar files under `skl/platforms/<id>.yaml`. The second sub-question is moot under the sidecar layout.

### ~~Q-010 - Variables (D-007) in master frontmatter: location and shape~~

D-007 commits to declarative `variables[]` per skill with substitution at deploy time. The analysis §7.3 proposes `skl.variables[]` with `name`, `description`, `required`, and an optional `default`. Open sub-questions were: variables home (`skl.variables[]` vs top-level), default-value home (inline vs tier-1 values), and validation timing (compile-time vs deploy-time).

Resolved by [SKL-004](decisions/SKL-004-master-skill-md-posture.md): `skl.variables[]` in SKILL.md frontmatter; defaults inline; declarations validated at compile time by `skl validate`, value resolution validated at deploy time per D-007. The validation-timing split falls out of existing mechanisms and does not need its own decision record.

### ~~Q-011 - Multi-agent / handoff modelling: defer or specify now?~~

Several targets have first-class sub-agent / handoff support: M365 `worker_agents[]` (preview), VS Code `agents[]` + `handoffs[]`, Claude Code subagents, Claude Cowork bundles. The analysis §8.5 proposed deferring handoff modelling in the master shape to v0.2+.

Resolved by [SKL-005](decisions/SKL-005-defer-handoff-modelling.md): defer. v0.1 does not model `skl.handoffs[]`; authors fall back to platform-native fields inside sidecars (`skl/platforms/m365.yaml` `worker_agents`, `skl/platforms/vscode.yaml` `agents` / `handoffs`). The cross-platform abstraction lands in v0.2 once real authored evidence shows what shape it should take.
