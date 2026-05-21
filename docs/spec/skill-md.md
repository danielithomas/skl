# `SKILL.md` authoring contract

The source-of-truth authoring artefact for one skill. Specification for what authors write and what `skl` reads at validate / compile / deploy time. Decisions backing this contract:

- [`SKL-004`](../decisions/SKL-004-master-skill-md-posture.md) - Anthropic Skills base + `skl:` extensions + progressive sidecars.
- [`SKL-005`](../decisions/SKL-005-defer-handoff-modelling.md) - handoff modelling deferred to v0.2.
- [`SKL-006`](../decisions/SKL-006-strip-skl-block-on-skills-native-compile.md) - `skl:` block stripped on Skills-native compile; provenance comment emitted.
- [`SKL-008`](../decisions/SKL-008-persona-defaults-skills-format-refresh.md) - per-target persona defaults; Identity section conditionally required.
- [`SKL-009`](../decisions/SKL-009-m365-schema-versioning.md) - M365 `schema_version` pin.

## Folder layout

```
skills/<skill-kebab-name>/
├── SKILL.md                             # source of truth
├── knowledge/                           # knowledge contracts referenced from frontmatter
│   └── <contract>.contract.md
├── references/                          # Anthropic-Skills convention (optional)
├── scripts/                             # Anthropic-Skills convention (optional)
├── assets/                              # Anthropic-Skills convention (optional)
├── tests/
│   └── test-cases.yaml                  # consumed by `skl test` (v0.1 deferred to Stage 7)
├── skl/                                 # OPTIONAL - per-platform sidecars
│   └── platforms/
│       ├── copilot-studio.yaml
│       ├── m365.yaml
│       └── vscode.yaml
└── platforms/                           # compiler output (D-001, template-form per D-007)
    └── ...
```

A skill that targets only Skills-native surfaces (`claude-code` / `claude-cowork` / `ms-cowork`) needs no `skl/` directory - the SKILL.md alone is the entire authored surface.

## Frontmatter

YAML block fenced by `---` at the very top of `SKILL.md`. The schema is bundled at [`src/skl/schemas/skill.frontmatter.schema.json`](../../src/skl/schemas/skill.frontmatter.schema.json) and validated by `skl validate` Check 2.

### Anthropic base (top-level)

| Field | Required | Constraint | Notes |
|-------|----------|------------|-------|
| `name` | yes | Kebab, `^[a-z][a-z0-9-]{0,63}$`, ≤64 chars | Anthropic's hard cap |
| `description` | yes | ≤1000 chars | Tightened from Anthropic's 1024 to M365's 1000 for cross-platform compat. Anthropic loads the skill based on this text alone - be specific and trigger-oriented |

Unknown top-level keys are allowed: Anthropic may add future fields, and the bundled `compatibility:` / `author:` conventions pass through. The strict shape applies inside the `skl:` block.

### `skl:` block

| Field | Required | Type | Notes |
|-------|----------|------|-------|
| `schema_version` | yes | integer (currently `1`) | Schema version for the `skl:` block itself |
| `display_name` | yes | string | Human-readable; surfaced as the H1 in compiled artefacts |
| `status` | yes | enum `active` / `draft` / `deprecated` | `deprecated` set via `skl deprecate` |
| `enabled_platforms` | yes | array of platform IDs | Can be empty during scaffolding |
| `lifecycle` | no | string | Free-form business category (e.g. `business_development`) |
| `persona` | no | `{nickname, role}` | Surfaced on persona-surface targets only (per SKL-008) |
| `variables` | no | array of `{name, description, required, default?}` | Snake-case `name`; required defaults to false |
| `knowledge` | no | array of `{id, contract?}` | Kebab `id`; `contract` is a repo-relative path to a markdown contract file |
| `tools` | no | array of `{id}` | Snake-case `id` |

Handoffs are deliberately omitted in v0.1 (per SKL-005). Authors needing handoff-like behaviour write platform-native fields in the sidecars verbatim.

### Worked example

```yaml
---
name: casey-case-studies
description: |
  Retrieve and synthesise consulting case studies from the firm's library.
  Use PROACTIVELY when the user asks about past engagements, references,
  win themes, or capability statements.
skl:
  schema_version: 1
  display_name: Casey - Case Studies
  status: active
  lifecycle: business_development
  persona: { nickname: Casey, role: Case Studies Specialist }
  enabled_platforms: [copilot-studio, m365, claude-code, claude-cowork]
  variables:
    - { name: consulting_company, description: The firm running the skill, required: true }
    - { name: case_study_library_path, description: SharePoint path, required: true }
  knowledge:
    - id: case-study-library
      contract: knowledge/case-studies.contract.md
  tools:
    - id: web_fetch
---
```

## Body sections

The body is markdown. H2 headers (`## SectionName`) are the anchors compilers care about. The order below matches the recommended structure; what's **required** depends on the platforms the skill targets.

| Section | Required when | Notes |
|---------|---------------|-------|
| `# {{display_name}}` | always | Identification, not a persona section. Compilers use this for the artefact title |
| `## Identity` | targeted platforms include Copilot Studio, or VS Code with a sidecar | Persona block. Stripped for Skills-native targets at compile (per SKL-008) |
| `## Capabilities` | always | What this skill can / cannot do |
| `## Knowledge Sources` | `skl.knowledge[]` is non-empty | References declared knowledge IDs |
| `## Tools` | `skl.tools[]` is non-empty | References declared tool IDs |
| `## Workflow` | always | Step-by-step procedure |
| `## Edge Cases` | always | Failure modes (including "no results" paths) |
| `## Examples` | always | At least one complete worked example; critical for triggering |
| `## Tone` | optional | Style guidance; often inlined into Identity |
| `## Output Format` | optional | When output structure matters |
| `## Response Templates` | optional | Verbatim response strings as guardrails |
| `## Validation Checklist` | optional | Pre-deployment checks the author runs manually |
| `## References` | optional | Pointer block to `references/` files |

H2 lines inside fenced code blocks are not treated as section headers.

## Per-platform sidecars

Live at `<skill_root>/skl/platforms/<platform-id>.yaml`. Each sidecar's shape is governed by its bundled schema (see [`src/skl/schemas/platforms/`](../../src/skl/schemas/platforms/)). Only platforms that need binding declarations or per-platform overrides get a sidecar:

| Platform ID | Sidecar required? | Notes |
|-------------|-------------------|-------|
| `claude-code`, `claude-cowork`, `ms-cowork` | no | Skills-native; compile is essentially a copy |
| `copilot-studio` | yes if bindings declared | Maps `skl.knowledge[].id` / `skl.tools[].id` to Copilot Studio UI source / connector names |
| `m365` | always when targeted | Requires `schema_version` per SKL-009; carries bindings and M365-specific fields (behaviour overrides, conversation starters, disclaimer, etc.) |
| `vscode` | optional - presence triggers Custom Agent variant | Per [SKL-007](../decisions/SKL-007-vscode-emit-skill-and-custom-agent.md). `emit_skill: false` suppresses the Skill variant |

Binding cross-reference: every `bindings.knowledge.<id>` / `bindings.tools.<id>` in a sidecar must match an `id` declared in the master `skl.knowledge[]` / `skl.tools[]`. `skl validate` errors on mismatch.

`skl validate` warns when `enabled_platforms` includes a non-Skills-native target that lacks a sidecar **and** the skill declares any bindings - the bindings will not land in the compiled artefact otherwise.

## Variables and tokens

`skl.variables[]` declarations support `{{variables.X}}` tokens in the body and in any sidecar string. Resolution is deferred to deploy time (per [D-007](../decisions/D-007-three-tier-values.md)); compile emits template-form artefacts with tokens intact.

`{{ variables.x }}` (with whitespace) is accepted alongside `{{variables.x}}`.

`skl validate` Check 7 errors on any token whose variable is not declared. `skl lint` warns on the same condition for in-progress edits.

## Scaffolding

`skl init <skill-kebab-name> [--platform <id>]...` from inside an existing skill-host repo creates:

- `skills/<skill-kebab-name>/SKILL.md` from the kit's `_shared/templates/standalone-skill.md` (falling back to the bundled copy in `src/skl/templates/`). `{{NAME}}`, `{{DISPLAY_NAME}}`, `{{ENABLED_PLATFORMS}}` are substituted.
- One sidecar stub per non-Skills-native `--platform` target.

The scaffold's `status: draft`, `enabled_platforms: [...]`, and load-bearing H2 sections are pre-populated; the author fills in the TODO content. The scaffolded skill passes `skl validate` against the bundled fallback kit.

## What gets stripped at compile

[SKL-006](../decisions/SKL-006-strip-skl-block-on-skills-native-compile.md) governs the Skills-native compile path:

- The whole `skl:` frontmatter block is stripped; only Anthropic-standard fields remain.
- The compiled SKILL.md leads with a `# Compiled by skl <version> from <source> on <date>` provenance comment.
- The `## Identity` body section is stripped where SKL-008 says strip.

Non-Skills-native compilers (Copilot Studio, M365) emit entirely different file formats; SKL-006 frontmatter strip does not apply, but the provenance comment convention does.
