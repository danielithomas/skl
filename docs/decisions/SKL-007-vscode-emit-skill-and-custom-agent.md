# SKL-007 - VS Code emits Skill + Custom Agent variants; never emits `.chatmode.md`

| Field | Value |
|-------|-------|
| **ID** | SKL-007 |
| **Date** | 21 May 2026 |
| **Status** | Final |
| **Owner** | Daniel Thomas |
| **Raised in** | [`docs/analysis/skills-spec.md`](../analysis/skills-spec.md) §8.2 |
| **Resolves** | [Q-008](../open-questions.md#q-008---vs-code-agent-skill-custom-agent-or-both) |
| **Builds on** | [SKL-004](./SKL-004-master-skill-md-posture.md) (sidecar-presence as opt-in signal) |

## Question

VS Code natively consumes two distinct skill-like formats that coexist in the same installation:

- **Agent Skill** at `.github/skills/`, `.claude/skills/`, `.agents/skills/`, etc. - standard Anthropic SKILL.md. On-demand. No persistent persona. Open standard, portable across surfaces.
- **Custom Agent** at `.github/agents/<name>.agent.md` - VS-Code-specific (also accepted by Claude Code via `.claude/agents/`). Persistent persona. Tool allow-list. Model preference. `handoffs[]`, `agents[]`, `hooks`. Richer frontmatter, body serves as system prompt.

[SKL-004](./SKL-004-master-skill-md-posture.md) settled that the opt-in signal for Custom Agent emission is "does `skl/platforms/vscode.yaml` exist?". Three sub-questions remained:

1. When the sidecar exists, do we emit **both** variants or **only Custom Agent**?
2. Should the legacy `.chatmode.md` format ever be emitted?
3. Should this decision settle body-content rules (persona stripping, Identity-section handling) for VS Code, or leave that to [Q-009](../open-questions.md#q-009---persona-stripping-defaults-per-target-in-light-of-skills-format-having-no-persona-field)?

There is also a related risk noted in [`docs/analysis/skills-spec.md`](../analysis/skills-spec.md) §10: VS Code is mid-rename from `.chatmode.md` to `.agent.md`; the legacy format is still accepted but no longer the primary path.

## Decision

Three pieces:

**1. Emit policy.**

- **No `skl/platforms/vscode.yaml` sidecar** (and `vscode` listed in `enabled_platforms`): emit the Skill variant only at `platforms/vscode/skill/<skill>/SKILL.md`. The skill behaves as a plain Anthropic Agent Skill on VS Code's skill-loading surfaces.
- **Sidecar present**: emit **both** variants by default - the Skill variant at `platforms/vscode/skill/<skill>/SKILL.md` and the Custom Agent variant at `platforms/vscode/agent/<skill>.agent.md`. Author can suppress Skill emission with `emit_skill: false` in the sidecar.
- The Custom Agent variant is always `.agent.md`. **`.chatmode.md` is never emitted**, including via opt-in.

**2. Custom Agent frontmatter composition.**

The Custom Agent's frontmatter is built from the master SKILL.md plus the sidecar:

| Custom Agent field | Source |
|---|---|
| `description` | Master SKILL.md `description` |
| `name` | Master SKILL.md `name` (defaults to filename if absent) |
| `target` | `skl/platforms/vscode.yaml` `target` (`vscode` or `github-copilot`) |
| `model` | `skl/platforms/vscode.yaml` `model` |
| `tools` | `skl/platforms/vscode.yaml` `bindings.tools` values (the VS Code tool names declared per-ID) plus any explicit `tools` array in the sidecar |
| `agents` | `skl/platforms/vscode.yaml` `agents` |
| `handoffs` | `skl/platforms/vscode.yaml` `handoffs` (platform-native, per [SKL-005](./SKL-005-defer-handoff-modelling.md)) |
| `hooks` | `skl/platforms/vscode.yaml` `hooks` |
| `mcp-servers` | `skl/platforms/vscode.yaml` `mcp-servers` |
| `user-invocable`, `disable-model-invocation`, `argument-hint` | Sidecar, passed through verbatim if declared |

The body is the same markdown as the source SKILL.md body, subject to body content rules settled by Q-009 (see below).

**3. Body content rules.**

Out of scope for this decision. Q-008 governs which files are emitted and how their frontmatter composes; body content rules - including whether the `## Identity` section is stripped from the Skill variant but retained in the Custom Agent variant, and how persona inlines into either - are settled by [Q-009](../open-questions.md#q-009---persona-stripping-defaults-per-target-in-light-of-skills-format-having-no-persona-field) uniformly across all targets. Both variants apply Q-009's rules to their respective surfaces; nothing in this decision pre-empts Q-009.

The provenance comment from [SKL-006](./SKL-006-strip-skl-block-on-skills-native-compile.md) lands on both variants.

## Rationale

**Why both variants by default (when sidecar exists).**

- **The Skill variant is free at compile time.** It is the same byte-stream already being produced for `platforms/claude-code/`, `platforms/claude-cowork/`, `platforms/ms-cowork/`. Emitting it to `platforms/vscode/skill/` is a copy.
- **Hedge against the consuming environment.** A skill-host repo consumed in plain GitHub Copilot (no Custom Agent support), in VS Code with Custom Agents, or via Claude Code on the same machine all see different subsets of these formats. Defaulting to "both" maximises reach with zero authoring cost.
- **The two surfaces are visually distinct.** Agent Skills surface through VS Code's skill selector; Custom Agents through the chatmode picker. Double-listing risk is low; conflating them with a single artefact is the more confusing failure mode.

**Why opt-out (`emit_skill: false`) rather than no opt-out at all.**

There are real cases where an author wants the Custom Agent to be the only surface - tool restrictions need to apply, the persistent persona is core to the design, or the skill genuinely makes no sense as an on-demand capability. The flag costs almost nothing in the sidecar schema and gives those cases an exit. We do not provide an inverse "Custom Agent only when also opt-in via flag" because the sidecar's existence is already the opt-in (per SKL-004).

**Why never emit `.chatmode.md`.**

VS Code's own migration documentation flags `.chatmode.md` as legacy. The expanded frontmatter (`handoffs`, `agents`, `hooks`, `target`, `mcp-servers`) is `.agent.md`-only. Shipping to `.chatmode.md` means shipping to a format that is on the way out, with a strict feature subset, for the benefit of users on older VS Code. The carry cost - a second emission path, a second body-composition pass, a flag in the sidecar, ongoing schema-divergence handling - outweighs the temporary user benefit. Users on older VS Code can update; if a real case emerges where they cannot, `.chatmode.md` emission is easily added in a later minor version.

**Why body rules belong with Q-009, not here.**

Persona / Identity-section handling is a cross-cutting concern: Copilot Studio surfaces persona inline, M365 surfaces it inline, Claude-family targets strip it. VS Code's two variants happen to fall on opposite sides of that line (Skill variant aligns with Claude-family stripping; Custom Agent aligns with Copilot Studio / M365 surfacing). Resolving persona policy *inside* Q-008 would either duplicate Q-009 or pre-empt it. Cleaner to leave Q-008 about which files get emitted, and let Q-009 govern what they contain.

## What this constrains in `skl`

- `_shared/schemas/platforms/vscode.schema.json` (per SKL-004) gains an optional `emit_skill` boolean field, default `true`. When absent or `true`, both variants are emitted; when `false`, only the Custom Agent variant is emitted.
- The VS Code compiler is two stages:
  1. **Skill stage** - if `emit_skill` is not `false` and `vscode` is in `enabled_platforms`, emit `platforms/vscode/skill/<skill>/SKILL.md` (and the rest of the Anthropic-Skill folder: `scripts/`, `references/`, `assets/`). Subject to [SKL-006](./SKL-006-strip-skl-block-on-skills-native-compile.md) (strip `skl:`) and Q-009 (body rules).
  2. **Custom Agent stage** - if the sidecar exists, emit `platforms/vscode/agent/<skill>.agent.md` with frontmatter composed per the table above and body taken from SKILL.md modulo Q-009 rules.
- The Custom Agent's `tools` array is composed from `bindings.tools` values declared in the sidecar. The master `skl.tools[]` carries IDs only (per SKL-004); the sidecar's `bindings.tools` maps each ID to a VS Code tool name; those names land in the Custom Agent frontmatter.
- `skl validate` enforces:
  - If `vscode` is in `enabled_platforms` but no sidecar exists, the skill compiles cleanly to Skill variant only - no warning needed.
  - If the sidecar exists, `bindings.knowledge` and `bindings.tools` IDs cross-check against `skl.knowledge[]` / `skl.tools[]` declarations in the master frontmatter (already required by SKL-004).
  - If the sidecar declares `emit_skill: false` and `vscode` is the *only* enabled platform with no other Skills-native emission, no error - that's a valid Custom-Agent-only skill. Just a warning if the implicit "Custom Agent only" choice loses some portability the author might not have intended.
- `.chatmode.md` is never emitted under any flag or sidecar setting in v0.x. Adding it later requires a new decision record.
- `skl init` repo-scoped form with a `--platform vscode` flag (or the equivalent `skl add-platform vscode`) scaffolds `skl/platforms/vscode.yaml` with `emit_skill: true` and stubs for `target`, `model`, `tools`, `bindings`.

## See also

- [`docs/analysis/skills-spec.md`](../analysis/skills-spec.md) §4.7 (Custom Agent format), §8.2 (compilation strategy), §10 (risk on `.chatmode.md` deprecation).
- [`SKL-004`](./SKL-004-master-skill-md-posture.md) - the sidecar-as-opt-in-signal rule this decision builds on.
- [`SKL-005`](./SKL-005-defer-handoff-modelling.md) - `handoffs[]` in the VS Code sidecar is platform-native verbatim; cross-platform abstraction deferred to v0.2.
- [`SKL-006`](./SKL-006-strip-skl-block-on-skills-native-compile.md) - the Skill variant emitted here is subject to the strip rule and provenance comment.
- [Q-009](../open-questions.md#q-009---persona-stripping-defaults-per-target-in-light-of-skills-format-having-no-persona-field) - sibling decision governing body content for both variants emitted here.
