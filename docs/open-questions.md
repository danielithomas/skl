# Open questions

Live questions and decisions-in-flight for `skl`. Each entry stays here forever - the audit trail of "what we discussed and why we picked X" is more useful than a clean slate. When a question lands a decision, its heading gets struck through and a "Resolved by" link points at the [decision file](decisions/).

## Conventions

- IDs are `Q-NNN`, local to this repo, numbered in order they were raised.
- Resolved questions are kept under "Resolved", in numeric order, with strikethrough on the heading and a link to the deciding [SKL-NNN](decisions/) record.
- A decision can resolve several questions; an open question can spawn several decisions and stay open until all are settled.
- Cross-link liberally between this file, decision files, and the PR or conversation that raised the question.

---

## Open

### Q-004 - Global `skl_version` compatibility guard: edge cases

The guard added in [SKL-003](decisions/SKL-003-global-compatibility-guard.md) fires on every invocation inside a skill-host repo, except `skl init` and `skl validate` which have their own handling. Several edge cases need a follow-up call before they bite:

- **Escape hatch.** Should there be an `SKL_IGNORE_COMPAT=1` env var or `--ignore-compat` flag for emergency cases - e.g. a user needs to run one urgent fix but the manifest's pinned range excludes the installed `skl`? If yes, scope - per-command, global, or only on certain commands?
- **Unparseable manifest.** Currently the guard silently skips when the manifest fails to parse, letting `skl validate` surface the parse error. Right call, or should the guard fail fast with a more descriptive "can't even parse your manifest, run `skl validate`" message?
- **`skl --version`.** Click currently exits before the group callback when `--version` is processed, so the guard does not fire for that flag. Should we make the exemption explicit in the skip list / documentation, in case click's behaviour changes?
- **Skip-list extensions.** Are there other commands that should join the skip list later? `skl deprecate` is one candidate (user might be marking a skill deprecated *because* of the version mismatch). `skl shared sync` is another (the very command that could fix the situation by pulling a newer kit). Currently both fire the guard.

Raised: 2026-05-17, during PR #5 review.

---

### Q-005 - Master SKILL.md posture: Anthropic-Skills base with `skl:` extensions, or fully bespoke superset?

[`analysis/skills-spec.md`](analysis/skills-spec.md) §7 lands on **Anthropic Skills format as the base layer + `skl:` namespaced extensions for the superset surface**. The reasoning: five of six target platforms already accept Anthropic SKILL.md directly, so taking the open standard as the base means the four Skills-native targets compile for free.

Alternatives still on the table:
- Fully bespoke `skl` schema (top-level fields for everything; `name` / `description` happen to coincide with Anthropic's). Cleaner internal model, loses the "valid Anthropic Skill out of the box" property.
- Anthropic-Skills-only (no `skl:` extensions). Forces all non-Skills targets to derive everything from `description` + body. Pure but loses the binding declarations the non-Skills compilers need.

This needs to become a decision record (SKL-NNN) before `skl init` repo-scoped form lands. Whichever way it goes, it shapes the JSON Schema, the scaffolding template, and the validator.

Raised: 2026-05-18, by the skills spec analysis.

---

### Q-006 - Frontmatter namespacing for `skl`-added fields

If we accept the §7.3 proposal in [`analysis/skills-spec.md`](analysis/skills-spec.md), `skl` adds metadata to the SKILL.md frontmatter under a single `skl:` top-level key. Two questions follow:

- Is `skl:` the right namespace? Alternatives: `x-skl:`, separate top-level keys with `skl-` prefix (`skl-knowledge:`, `skl-tools:`), or a sibling `skill.config.yaml` file alongside SKILL.md.
- Should per-platform sub-blocks (`m365:`, `vscode:`, ...) live under `skl:` (`skl.m365`) or top-level (`m365:`)? Top-level reads cleaner; risks collision with future Anthropic / VS Code / Microsoft additions to the SKILL.md frontmatter spec. Under-`skl:` is collision-safe but verbose.

Raised: 2026-05-18, by the skills spec analysis. Linked to [[Q-005]].

---

### Q-007 - Compiled artefacts for Skills-native targets: strip `skl:` block or pass through?

For `claude-code`, `claude-cowork`, `ms-cowork` (and any future Skills-consuming surface), compile is essentially a copy. Question: do we strip the `skl:` frontmatter block from the compiled SKILL.md, or pass it through?

- **Strip:** cleaner artefact; downstream consumers see only the Anthropic-standard fields they know. Risk: someone re-imports the compiled artefact into a skill-host repo and loses the metadata.
- **Pass through:** Anthropic ignores unknown keys; harmless. The compiled artefact is identical to source modulo variable substitution.

Default-strip vs default-pass affects what `skl deploy` produces and what users see in `platforms/claude-code/SKILL.md`. Resolve before the compiler implementation lands.

Raised: 2026-05-18, by the skills spec analysis. Linked to [[Q-005]] and [[Q-006]].

---

### Q-008 - VS Code: Agent Skill, Custom Agent, or both?

VS Code natively consumes both Anthropic Agent Skills (`.github/skills/`, `.claude/skills/`) and Custom Agents (`.github/agents/<name>.agent.md`). The two are layered, not interchangeable:

- **Agent Skill** - portable across surfaces, on-demand, no persistent persona.
- **Custom Agent** - VS-Code-specific (and Claude Code via `.claude/agents/`), persistent persona, tool restrictions, model preference, handoffs to sibling agents.

[`analysis/skills-spec.md`](analysis/skills-spec.md) §8.2 proposes that authors opt in to the Custom Agent variant by declaring a `vscode:` (or `skl.vscode:`) block in master frontmatter; by default, only the Skill variant is emitted. Questions:

- Is opt-in the right default? Could default to "emit both" since the Skill variant is essentially free.
- If both are emitted, does the Custom Agent body include the persona block while the Skill body does not? Or do both bodies match and persona handling differs at install time?
- Should the `.chatmode.md` legacy format ever be emitted, or do we go straight to `.agent.md` per VS Code's migration?

Raised: 2026-05-18, by the skills spec analysis. Touches [[Q-009]] (persona) and the legacy [`compilation.md`](spec/compilation.md) §`vscode` row.

---

### Q-009 - Persona stripping defaults per target, in light of Skills format having no persona field

The Anthropic Skills format does not model persona as a first-class field; persona lives inline in the body, and the convention is to keep skills focused on a capability rather than a personality. The existing parent-project decision (D-006) sets per-platform persona-surfacing defaults that predate the Skills format.

The analysis (§7.3, §8.1) proposes: Skills-native compile strips the Identity body section (since Claude is the persona on those surfaces); Copilot Studio / M365 / VS Code keep it. Open questions:

- Refresh D-006 to account for Skills-native targets explicitly, or treat the existing defaults as already correct because Claude-family targets were already "strip"?
- For VS Code, persona handling depends on Q-008. If we ship both Skill and Custom Agent variants, do they treat persona differently?
- Should the per-skill override `skl.persona.strip_for: [platform-id, ...]` exist from day one, or is it premature?

Raised: 2026-05-18, by the skills spec analysis. Refers to D-006 in the parent project.

---

### Q-010 - Variables (D-007) in master frontmatter: location and shape

D-007 commits to declarative `variables[]` per skill with substitution at deploy time. The analysis §7.3 proposes `skl.variables[]` with `name`, `description`, `required`, and an optional `default`. Open questions:

- Is `skl.variables[]` the right home, or should variables sit at the top level (`variables:`) of the SKILL.md frontmatter? Top-level matches how the existing spec narrative talks about them.
- Should the default value be inline in the frontmatter, or always live in tier-1 values (`_shared/skill.config.yaml`) and be referenced by key? Inline is friendlier; tier-1 is more consistent with D-007.
- How are variables validated at compile time vs deploy time? Compile checks declarations exist; deploy checks values resolve. Where does the type-checking sit?

Raised: 2026-05-18, by the skills spec analysis. Anchors on D-007.

---

### Q-011 - Multi-agent / handoff modelling: defer or specify now?

Several targets have first-class sub-agent / handoff support: M365 `worker_agents[]` (preview), VS Code custom agent `agents[]` + `handoffs[]`, Claude Code subagents (`.claude/agents/`), Claude Cowork bundles. D-009 already declares MAS composition a cross-repo concern.

The analysis §8.5 proposes deferring handoff modelling in the master shape to v0.2+ and carrying handoffs as a placeholder for v0.1. Question: is this the right call, or does shipping `skl` v0.1 without a handoff model bake a workaround that we then have to migrate later? A reasonable v0.1 minimum could be `skl.handoffs[]: [{target: <skill-name>, when: <desc>}]` with each compiler projecting as it can.

Raised: 2026-05-18, by the skills spec analysis. Anchors on [`D-009`](decisions/D-009-multi-repo-architecture.md).

---

### Q-012 - M365 declarative-agent schema versioning: how do we track Microsoft's iteration?

The M365 declarative-agent manifest has gone v1.3 -> v1.7 in ~6 months. We need a strategy:

- Bundle the JSON Schema in `_shared/schemas/declarative-agent-manifest-1.7.json` (per [[D-011]]) and pin a `schema_version` per skill (`skl.m365.schema_version: 1.7`)?
- Or always emit the latest known version and warn on missing-from-our-bundle?
- How does `skl validate` flag a manifest written for v1.6 when the bundled schema is v1.7?
- When v1.8 lands, is that a minor `skl` bump (new validation rules) or major (compiler output contract changed)? Per the existing `infrastructure.md` versioning policy it would be a minor bump if the v1.7 output stays valid.

Raised: 2026-05-18, by the skills spec analysis. Anchors on the M365 row in [`compilation.md`](spec/compilation.md).

---

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
