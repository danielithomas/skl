# SKL-008 - Per-target persona-surfacing defaults refreshed for the Skills-format era

| Field | Value |
|-------|-------|
| **ID** | SKL-008 |
| **Date** | 21 May 2026 |
| **Status** | Final |
| **Owner** | Daniel Thomas |
| **Raised in** | [`docs/analysis/skills-spec.md`](../analysis/skills-spec.md) §7.3, §8.1 |
| **Resolves** | [Q-009](../open-questions.md#q-009---persona-stripping-defaults-per-target-in-light-of-skills-format-having-no-persona-field) |
| **Supersedes** | D-006 persona-defaults table, for `skl`'s purposes (D-006 itself remains the parent-project record; this decision is the authoritative per-target table for what `skl` compiles) |
| **Builds on** | [SKL-006](./SKL-006-strip-skl-block-on-skills-native-compile.md), [SKL-007](./SKL-007-vscode-emit-skill-and-custom-agent.md) |

## Question

The Anthropic Agent Skills format does not model persona as a first-class field; the convention is to keep skills capability-focused, not personality-focused. D-006 (in the parent project) set per-platform persona-surfacing defaults *before* Skills became the cross-platform open standard - and the defaults it set treat Claude-family targets (claude-code, claude-cowork) as persona-surfacing surfaces, because Claude Code's earlier subagent format encouraged authored-agent style.

The May 2026 analysis reframes this: on Claude-family surfaces Claude is already the persona, and injecting "You are Casey, a Case Studies Specialist..." over the top is at best noise. Skills-native targets should strip the Identity body section by default. This conflicts with two cells of the existing D-006 table.

[SKL-007](./SKL-007-vscode-emit-skill-and-custom-agent.md) also split VS Code into two emitted variants (Agent Skill, Custom Agent), each of which needs its own persona position.

Three sub-questions to resolve:

1. Refresh D-006's per-target table or treat it as already correct?
2. How does persona land in VS Code's two variants?
3. Should `skl` ship a per-skill override (`skl.persona.surface_for` / `strip_for`) in v0.1?

## Decision

**1. Refreshed per-target persona default table.**

| Platform | Default | Was (D-006) | Reason |
|---|---|---|---|
| `copilot-studio` | **surface** | surface | Unchanged. Authored chatbot; persona is the product. Identity-first is universal across the legacy `prompt_library/` agents. |
| `m365` | strip | strip | Unchanged. Declarative agent; policy-oriented. The `instructions` field reads as a system policy, not a persona. |
| `ms-cowork` | strip | strip | Unchanged. Skills-native consumer. |
| `claude-code` | **strip** | surface | **Flipped.** Skills-native target. Claude is the persona; injecting an authored persona over the top is noise. |
| `claude-cowork` | **strip** | surface | **Flipped.** Same reasoning as `claude-code`. |
| `vscode` Skill variant | strip | (vscode strip) | Matches other Skills-native targets. Same byte-stream as `claude-code` / `claude-cowork`. |
| `vscode` Custom Agent variant | **surface** | (vscode strip) | New row per SKL-007. The Custom Agent surface is *defined by* persona, tool restrictions and persistent behaviour - persona is the differentiation from Skills. |

`_shared/skill.config.yaml` `personas.surface_in` continues to govern repo-level overrides (per D-006). The defaults above are what ships when the shared kit's `personas.surface_in` is left at its defaults.

**2. What "strip" and "surface" mean concretely.**

This is a body-section operation, not a frontmatter operation.

- **Strip**: the compiler removes the `## Identity` section wholesale from the body before emitting the artefact. Nothing else in the body is touched. The H1 (`# {{display_name}}`) is identification, not persona, and is never stripped. The `## Tone` section is style/voice guidance (AU spelling, no em-dashes, concise output) and is also not persona - it surfaces on every target if present.
- **Surface**: the `## Identity` section is retained in the compiled artefact. How it is positioned in the output is per-compiler:
  - `copilot-studio`: inlined as the opening paragraph of the `instructions.md` text, alongside Tone (per analysis §8.3).
  - `vscode` Custom Agent variant: retained as an explicit `## Identity` H2 at the top of the `.agent.md` body, which serves as system prompt. The `description` Custom Agent frontmatter field carries a one-liner only (per SKL-007), not the full persona block.
  - Any future "surface" target: retained as an H2, positioning at compiler discretion.

The frontmatter `skl.persona` block is stripped from compiled artefacts by [SKL-006](./SKL-006-strip-skl-block-on-skills-native-compile.md) regardless of persona-surfacing choice. `skl.persona` is an internal source field used by the compiler to scaffold Identity (when scaffolding from `skl init`) and to enforce the kebab-prefix-matches-nickname rule (per D-006); it does not appear in any compiled artefact.

**3. Per-skill override deferred to v0.2.**

`skl` v0.1 does not introduce `skl.persona.surface_for` or `skl.persona.strip_for` per-skill overrides. Authors who need different behaviour today have two existing mechanisms:

- **Repo-level**: edit `_shared/skill.config.yaml` `personas.surface_in` to flip a default across the whole skill-host repo.
- **Skill-level workaround**: inline persona content outside the `## Identity` section (e.g. in `## Tone` or `## Capabilities`) so the strip leaves it alone.

A per-skill override lands in v0.2 if authored evidence shows the workarounds are insufficient. Same posture as SKL-005 - defer the speculative abstraction until real authored evidence shapes it.

## Rationale

**Why flip claude-code and claude-cowork to strip.**

The earlier D-006 defaults predate the Anthropic Skills format becoming the cross-platform standard. They were set when Claude Code's subagent format felt more like an authored agent (with a `name` and `description` frontmatter that encouraged persona text in the body). The Skills format convention - and the published Anthropic skills themselves - keep skills capability-focused. Injecting an authored persona on a Claude-family surface where Claude is already operating creates one of two failures: either the model treats it as noise and the words are wasted, or the model takes it literally and starts answering "as Casey", which is often worse than answering as itself with Casey's capabilities. The right default on Claude-family surfaces is strip.

**Why surface stays for Copilot Studio.**

Authored evidence in the legacy `prompt_library/` is unambiguous: every Copilot Studio agent leads with Identity ("You are [Name], a [role]..."). The product expects an authored chatbot personality; surface remains the right default.

**Why M365 stays strip.**

M365 declarative agents are policy-oriented containers (`actions`, `data_sources`, `worker_agents`), with `instructions` read as a system policy rather than as a chat persona. D-006's strip default holds.

**Why VS Code splits into two rows.**

SKL-007 emits two artefacts for a skill that opts in to the Custom Agent variant. They go to two different VS Code surfaces with two different consumption models:

- Skill variant lands at `.github/skills/`, loaded on-demand alongside other Anthropic Skills. Same byte-stream as `claude-code` / `claude-cowork`. Strip matches.
- Custom Agent variant lands at `.github/agents/<name>.agent.md`, loaded as a persistent agent profile. The `.agent.md` body *is* the system prompt - which is exactly the case where persona belongs inline. Surface matches.

This is also internally consistent: the Custom Agent variant exists precisely because the author wanted persistent persona / tool restrictions / handoffs. Stripping the Identity from a Custom Agent variant would undo the reason for emitting it.

**Why defer the per-skill override.**

- Repo-level `personas.surface_in` already gives authors an escape hatch for the "this whole repo needs different behaviour" case.
- The skill-level workaround (move persona content out of `## Identity` so strip leaves it) is clunky but functional, and clunky is fine for an unproven need.
- Adding `skl.persona.surface_for: [platforms]` (or its inverse) commits us to a schema field we have to honour forever, before we know whether the field's shape is right. Same trap SKL-005 avoids for handoffs.
- If we see real evidence of a single skill needing per-target persona behaviour different from the repo default, v0.2 picks up the field cleanly with no migration cost.

## What this constrains in `skl`

- The compiler's persona-surfacing step (`compilation.md` compile order step 6) reads the resolved `personas.surface_in` from the shared kit; the defaults that resolve when nothing overrides are the per-target table above.
- The compiler removes the `## Identity` section wholesale when stripping. No partial-strip / first-paragraph-only behaviour. Identity is a single H2 section; either it is in the output or it is not.
- `## Tone` and `# {{display_name}}` (H1) are never affected by persona-surfacing. They are not persona.
- `skl validate`:
  - Continues to enforce the kebab-prefix rule (`name`'s first segment matches `persona.nickname` lowercased, per D-006) even when persona is stripped on every target the skill targets. The internal `skl.persona` source field still requires consistency.
  - Does not warn when a skill targets only strip targets and has no `## Identity` section. Identity remains "required for surface targets, optional otherwise" per the analysis §7.4 table.
  - Warns if a skill targets a surface target (`copilot-studio`, VS Code Custom Agent variant) and lacks an `## Identity` body section.
- The shared kit (`_shared/skill.config.yaml`) `personas.surface_in` continues to be the documented per-repo override mechanism. Authors who want a different default across their whole repo edit that file.
- No new frontmatter field is introduced. `skl.persona.surface_for` / `skl.persona.strip_for` are explicitly out of scope for v0.1.
- `docs/spec/compilation.md` per-platform table is updated to reflect the new defaults and to split the VS Code row into Skill variant and Custom Agent variant. This is a follow-up touch-up to the spec; the table here is the authoritative source.

## See also

- [`docs/analysis/skills-spec.md`](../analysis/skills-spec.md) §7.3 (persona scoping), §7.4 (body sections), §8.1 (Skills-native compile).
- [`SKL-006`](./SKL-006-strip-skl-block-on-skills-native-compile.md) - strips the frontmatter `skl.persona` block regardless of body persona handling.
- [`SKL-007`](./SKL-007-vscode-emit-skill-and-custom-agent.md) - introduces the VS Code Skill / Custom Agent split that this decision assigns persona defaults to.
- [`SKL-005`](./SKL-005-defer-handoff-modelling.md) - parallel deferral posture for handoffs; same reasoning applied to per-skill persona override.
- [`D-006`](https://github.com/danielithomas/ai-skills-lib/blob/main/analysis/06_decision_log.md) - parent-project decision this refreshes for `skl`'s purposes. The kebab-prefix rule, `personas.surface_in` mechanism, and `skl.persona` source-field convention all carry forward unchanged.
- [`docs/spec/compilation.md`](../spec/compilation.md) - per-platform table to be updated to match this decision.
