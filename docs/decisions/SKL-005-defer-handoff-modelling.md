# SKL-005 - Defer multi-agent / handoff modelling to v0.2+

| Field | Value |
|-------|-------|
| **ID** | SKL-005 |
| **Date** | 20 May 2026 |
| **Status** | Final |
| **Owner** | Daniel Thomas |
| **Raised in** | [`docs/analysis/skills-spec.md`](../analysis/skills-spec.md) §8.5 |
| **Resolves** | [Q-011](../open-questions.md#q-011---multi-agent--handoff-modelling-defer-or-specify-now) |

## Question

Several target platforms have first-class sub-agent / handoff support: M365 `worker_agents[]` (preview), VS Code custom agent `agents[]` + `handoffs[]`, Claude Code subagents (`.claude/agents/`), Claude Cowork bundles. D-009 declares MAS composition a cross-repo concern.

Should `skl` v0.1 model handoffs in the master SKILL.md shape, or defer until v0.2+? A reasonable v0.1 minimum would be `skl.handoffs[]: [{target: <skill-name>, when: <desc>}]` with each compiler projecting as best it can. The risk of deferral: shipping v0.1 without a handoff model could bake in a workaround we then have to migrate later.

## Decision

Defer. `skl` v0.1 does not model handoffs in the master schema. The `_shared/schemas/skill.frontmatter.schema.json` produced under [SKL-004](./SKL-004-master-skill-md-posture.md) does not include a `handoffs` field at the top level of `skl:` nor inside any per-platform sidecar schema for v0.1.

Authors who need handoff-like behaviour today fall back to platform-native mechanisms inside the per-platform sidecar's `behavior_overrides` / `worker_agents` / `agents` fields, written verbatim and unvalidated by `skl validate` beyond JSON-schema shape checks. The toolkit emits those fields into the compiled artefact as-is.

A handoff model lands as part of `skl` v0.2 work, after v0.1 ships and we have evidence from real skills about which shape the abstraction needs to take.

## Rationale

- **The shape is genuinely uncertain.** M365's `worker_agents[]` is preview (likely to change), VS Code's `handoffs[]` is recent, Claude Code subagents are a sibling concept rather than a handoff target, and Claude Cowork bundles are documented at the product level rather than the schema level. Picking a normalised cross-platform shape now means guessing at three of four moving targets.
- **No authored evidence yet.** The legacy `prompt_library/` agents do not use handoffs. The first real skill that needs them will tell us what the abstraction should look like; designing in advance produces an abstraction that fits no one.
- **Deferral is cheap.** Authors can still ship handoff-using skills in v0.1 by writing platform-native fields in the sidecars. They lose `skl validate`'s cross-platform consistency checks for handoffs, but they would lose those anyway against an abstraction we are not confident in.
- **Migration is cheap.** When v0.2 introduces `skl.handoffs[]`, we generate the same per-platform fields the authors are writing by hand today. The migration is a refactor at most, not a breaking change to existing skills.
- **D-009 already covers MAS composition.** Cross-repo multi-agent composition is named as a separate concern in D-009. v0.1 handoff modelling would have to coexist with whatever D-009 implies for MAS coordination; settling D-009 first is the right order of operations.

## What this constrains in `skl`

- The v0.1 `_shared/schemas/skill.frontmatter.schema.json` does **not** include a `handoffs` field. Adding one is a v0.2 task.
- Per-platform sidecar schemas (`skl/platforms/<id>.yaml`) allow platform-native handoff fields directly:
  - `skl/platforms/m365.yaml` accepts `worker_agents` per the M365 v1.7 manifest.
  - `skl/platforms/vscode.yaml` accepts `agents` and `handoffs` per the VS Code custom-agent schema.
  - Other platforms have no comparable field; nothing is added there.
- `skl validate` performs schema shape checks on the platform-native fields but does **not** cross-check that a referenced sibling skill exists, is enabled on the same platform, or has a compatible interface. Those checks come with v0.2.
- The v0.2 design will need to address whether `skl.handoffs[]` overrides or merges with platform-native fields when both are declared. Out of scope here.

## See also

- [`docs/analysis/skills-spec.md`](../analysis/skills-spec.md) §8.5 - the analysis that proposed deferral.
- [`SKL-004`](./SKL-004-master-skill-md-posture.md) - the master SKILL.md posture; this decision is a deliberate gap in that schema.
- [`D-009`](./D-009-multi-repo-architecture.md) - cross-repo MAS composition is the surrounding concern.
