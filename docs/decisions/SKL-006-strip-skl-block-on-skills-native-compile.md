# SKL-006 - Strip the `skl:` frontmatter block on Skills-native compile

| Field | Value |
|-------|-------|
| **ID** | SKL-006 |
| **Date** | 21 May 2026 |
| **Status** | Final |
| **Owner** | Daniel Thomas |
| **Raised in** | [`docs/analysis/skills-spec.md`](../analysis/skills-spec.md) §8.1 |
| **Resolves** | [Q-007](../open-questions.md#q-007---compiled-artefacts-for-skills-native-targets-strip-skl-block-or-pass-through) |

## Question

For Skills-native compile targets - `claude-code`, `claude-cowork`, `ms-cowork`, future claude.ai uploads, and any other surface that consumes Anthropic Agent Skills directly - compile is essentially `cp -R source platforms/<id>/`. The master SKILL.md frontmatter carries an `skl:` block (per [SKL-004](./SKL-004-master-skill-md-posture.md)) holding `schema_version`, `display_name`, `status`, `lifecycle`, `persona`, `enabled_platforms`, `variables[]`, and platform-agnostic `knowledge[]` / `tools[]` ID declarations.

When the compiler writes SKILL.md to `platforms/<id>/<skill>/SKILL.md`, does it strip the `skl:` block, pass it through verbatim, or selectively keep some keys?

The technical floor: either choice is safe. Anthropic only reads `description`; unknown top-level keys are ignored. The canonical `anthropics/skills/skill-creator/SKILL.md` itself carries unrecognised fields. So this is an ergonomics / hygiene call, not a correctness one. It does not cover body section handling (`## Identity` strip for Skills-native targets), which is entangled with persona-surfacing rules and is resolved alongside [Q-009](../open-questions.md#q-009---persona-stripping-defaults-per-target-in-light-of-skills-format-having-no-persona-field).

Three postures were on the table:

- **A. Strip all.** Remove the entire `skl:` key from compiled frontmatter. Compiled artefact is a clean Anthropic Skill carrying only Anthropic-standard fields.
- **B. Pass through.** Preserve `skl:` verbatim. Source and compiled frontmatter are byte-identical (modulo deploy-time variable substitution, which happens later per [D-007](./D-007-three-tier-values.md)).
- **C. Selective strip.** Drop toolkit-scaffolding keys (`knowledge`, `tools`, `variables`, `enabled_platforms`, `persona`, bindings) but keep publisher-style metadata (`display_name`, `lifecycle`, `status`). Cleaner than B, less surgical than A.

## Decision

Adopt posture **A: strip all**. Skills-native compile removes the entire `skl:` key from the compiled SKILL.md frontmatter, leaving only Anthropic-standard fields (`name`, `description`, and any future fields the open standard defines).

Provenance is preserved separately. Every compiled artefact - SKILL.md, `instructions.txt`, `declarative-agent.json`, regardless of target - gets a top-line provenance comment in the form:

```
# Compiled by skl <version> from <source-path> on <YYYY-MM-DD>
```

For SKILL.md the comment sits above the frontmatter fence. For JSON targets it lands as an adjacent sibling line or in a `$comment` field where the schema allows. This convention applies across all compilers, not only Skills-native; it is included in this decision because the strip-all posture makes it load-bearing for provenance recovery.

## Rationale

**Why strip over pass-through.**

- **Reverse-trip footgun.** Once compiled skills are committed under `platforms/<id>/` per D-001, someone *will* copy one into a new skill-host repo as a starting point. With strip-all, the new repo's `skl validate` rejects the file loudly (missing `skl:` block on what looks like a source SKILL.md) and the author has to re-declare scaffolding cleanly. With pass-through, the new repo silently inherits IDs, bindings, and `enabled_platforms` values that refer to a different host's `_shared/` and sidecars. Nothing trips until deploy time, and the failure mode is harder to read.
- **Compiled artefact's job is to be a clean Anthropic Skill.** The `skl:` block is build-tool scaffolding; it has no consumer at the destination. Anthropic's own published skills carry publisher-owned metadata (`compatibility:`), not their build tool's internal config. Strip-all keeps that distinction clean: publisher metadata flows through, toolkit scaffolding does not.
- **Symmetry across compilers.** Copilot Studio and M365 compilers emit entirely different formats (single `instructions` string, `declarative-agent.json`) and carry no `skl:` echo by construction. Skills-native compile should match: "compiled artefacts never carry toolkit config" is a flat rule, easier to reason about than "Skills-native targets retain it, others don't".
- **Information hygiene.** `skl:` may carry `lifecycle`, internal `knowledge[]` / `tools[]` IDs, variable names with descriptions. None secret, but internal vocabulary that need not ship with every artefact downstream consumers see.

**Why not selective strip (option C).**

Selective strip introduces a third schema - "what survives strip" - that has to be maintained as the `skl:` block grows. New keys would need an explicit strip-or-keep ruling each time. Strip-all and pass-all are both stable defaults; the middle ground has ongoing schema churn cost for no clear win. If a future Anthropic Skills field overlaps with something we currently strip (say Anthropic adds a `lifecycle:` field), we surface that field by lifting it out of `skl:` and into the Anthropic-standard area of the frontmatter, not by adding a passthrough exception.

**Why the provenance comment is part of this decision.**

Strip-all removes the most natural place to record "this artefact came from source X compiled by skl version Y". Without a provenance marker the compiled artefact is decoupled from the build context, which makes debugging harder. A one-line comment is the minimum-cost fix and is useful enough to extend to every compiler, not only Skills-native. Putting the convention in this record means it cannot be omitted as an implementation detail.

**The counter-argument worth naming.**

Pass-through has integrity: "the compiled artefact is the source, minus only what the target cannot consume". Under pass-through, an author debugging a deployed skill can read `platforms/claude-code/foo/SKILL.md` and see the whole declared world. Strip-all forces them back to source. The trade-off was judged the right way because (a) reading compiled artefacts is rare, the source is right there, and (b) the reverse-trip footgun bites strangers more than authors, and strangers are less able to diagnose silent stale state.

## What this constrains in `skl`

- The Skills-native compilers (`skl compile claude-code`, `skl compile claude-cowork`, `skl compile ms-cowork`, and any future Skills-consuming target) strip the entire `skl:` top-level key from frontmatter before writing the compiled SKILL.md. No selective preservation.
- Every compiler - Skills-native and otherwise - emits a top-line provenance comment of the form `# Compiled by skl <version> from <source-path> on <YYYY-MM-DD>`. Format details (timezone of date, source-path style relative vs absolute) are implementation-level and tracked in the compiler implementation, not here.
- `skl validate` does not need an "is this a compiled artefact?" detection rule. Compiled artefacts under `platforms/` are not in scope for `skl validate` (which targets source SKILL.md only); if someone copies a stripped compiled artefact into a source location, validate's existing "missing required `skl:` block" check is what surfaces the mistake. No special handling required.
- The strip happens after variable resolution (per D-007) and after any sidecar merge, not before. The compiler reads source SKILL.md + sidecars, resolves to an in-memory model, performs target-specific transformations, then emits to disk with `skl:` removed for Skills-native targets.
- If a future Anthropic Skills standard adds fields that overlap with `skl:` keys (e.g. `lifecycle:`), the path forward is to lift the field out of `skl:` into the Anthropic-standard frontmatter area at the source, not to add per-key passthrough exceptions to this strip rule.

## See also

- [`docs/analysis/skills-spec.md`](../analysis/skills-spec.md) §8.1 - the analysis that raised this question.
- [`SKL-004`](./SKL-004-master-skill-md-posture.md) - defines the `skl:` block this decision strips.
- [`D-001`](https://github.com/danielithomas/ai-skills-lib/blob/main/analysis/06_decision_log.md) - compiled `platforms/` artefacts are committed (this decision shapes what gets committed).
- [`D-007`](./D-007-three-tier-values.md) - variable substitution at deploy time (compile produces template-form artefacts, then strips).
- [Q-009](../open-questions.md#q-009---persona-stripping-defaults-per-target-in-light-of-skills-format-having-no-persona-field) - body-side persona / Identity-section stripping; sibling concern, resolved separately.
