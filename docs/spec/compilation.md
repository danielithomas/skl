# Compilation: per-platform compilers and validators

How `skl compile` turns a single SKILL.md into platform-specific artefacts, and what `skl validate` checks before, during and after. Distilled from D3 §6 and §7.

---

## Overview

`skl compile` produces template-form artefacts (per D-007) under each skill's `platforms/` directory. Substitution and deploy are handled separately by `skl deploy`; this document covers compilation only.

```
skills/casey-case-studies/
├── SKILL.md                                  ← source of truth
├── knowledge/
│   └── case-studies.contract.md
├── tests/test-cases.yaml
└── platforms/                                ← compiler output, committed, template-form
    ├── copilot-studio/instructions.md
    ├── m365/manifest.json
    ├── ms-cowork/casey-case-studies/SKILL.md  ← Anthropic Agent Skill folder
    ├── claude-code/casey-case-studies/SKILL.md
    ├── claude-cowork/casey-case-studies/SKILL.md
    └── vscode/
        ├── skill/casey-case-studies/SKILL.md  ← Agent Skill variant
        └── agent/casey-case-studies.agent.md  ← Custom Agent variant (if sidecar present)
```

---

## Six target platforms

| Platform ID | Output shape | Character budget | Notes |
|-------------|--------------|------------------|-------|
| `copilot-studio` | Single markdown file with T-C-R structure | 8,000 chars (hard) | Copilot Studio's instructions field is the only target. Persona surfaces by default |
| `m365` | JSON manifest + accompanying markdown | 8,000 chars (hard) for instructions field | M365 Copilot declarative agent format. Persona strips by default |
| `ms-cowork` | Anthropic Agent Skill folder | none (warn > 50K) | Microsoft Cowork product. Skills-native consumer (compile is essentially a copy). Persona strips by default |
| `claude-code` | Anthropic Agent Skill folder | none (warn > 50K) | Skills-native consumer. Persona strips by default |
| `claude-cowork` | Anthropic Agent Skill folder | none (warn > 50K) | Skills-native consumer. Persona strips by default |
| `vscode` (Skill variant) | Anthropic Agent Skill folder at `platforms/vscode/skill/` | none (warn > 50K) | Loaded from `.github/skills/` etc. Persona strips by default. Emitted whenever `vscode` is in `enabled_platforms` and `emit_skill: false` is not set |
| `vscode` (Custom Agent variant) | `.agent.md` file at `platforms/vscode/agent/` | none (warn > 50K) | Loaded from `.github/agents/`. Persona surfaces by default. Emitted when `skl/platforms/vscode.yaml` sidecar exists |

The persona surface defaults are governed by [SKL-008](../decisions/SKL-008-persona-defaults-skills-format-refresh.md), which refreshes D-006's per-target table for the Anthropic Skills format era. Repo-level overrides live in `_shared/skill.config.yaml` `personas.surface_in` (per D-006). The VS Code two-variant split comes from [SKL-007](../decisions/SKL-007-vscode-emit-skill-and-custom-agent.md).

---

## Compiler contract

Every compiler accepts the same input shape and produces the same output shape:

### Input

- A parsed SKILL.md (frontmatter + canonically-ordered body sections).
- The skill's knowledge contracts (parsed).
- The shared kit (`_shared/`).
- The skill-host repo manifest (`skill-repo.yaml`).

### Output

- A template-form artefact at the platform's documented path under `platforms/<platform-id>/`.
- A list of compile-time warnings (e.g. "tool `web_fetch` bound to `Web Fetch` on Copilot Studio - confirm the connector is installed").

### Properties

- Compilers do not write outside their own `platforms/<platform-id>/` directory.
- Compilers do not perform value substitution. Tokens remain.
- Compilers do not read or write secrets.
- Compilers are deterministic: same input produces byte-identical output.

---

## Compilation order

1. **Frontmatter parse.** Read and validate `SKILL.md` frontmatter against the schema in `_shared/schemas/skill.frontmatter.schema.json`.
2. **Body parse.** Split the body on canonical section anchors: Identity, Tone, Capabilities, Knowledge Sources, Tools, Workflow, Output Format, Edge Cases, Examples, Validation Checklist.
3. **Knowledge contract resolution.** For each knowledge ID referenced in frontmatter or body, load the corresponding contract and resolve per-platform bindings.
4. **Tool binding resolution.** For each tool ID, look up the per-platform binding map in frontmatter.
5. **Per-platform compilation.** Run each enabled platform's compiler.
6. **Per-platform persona surfacing.** Apply or strip persona based on `personas.surface_in`.
7. **Budget check.** Run `skl budget` against each artefact; fail compilation if any hard budget is exceeded.
8. **Write outputs** under `platforms/<platform-id>/`.

Steps 1-4 produce a normalised intermediate representation (IR). Each platform compiler reads the IR; it does not re-parse the SKILL.md.

---

## Per-platform compilers

### `copilot-studio`

- **Output**: `platforms/copilot-studio/instructions.md`, a single markdown file structured per the T-C-R framework (Tone, Capabilities, Rules).
- **Budget**: 8,000 characters, hard. Compilation fails if exceeded.
- **Persona**: surfaces by default.
- **Tool / knowledge bindings**: rendered into the body as platform-recognised references (SharePoint library names for knowledge; connector names for tools).
- **Notes**: Copilot Studio's instructions field is the only target. There is no manifest file. Live testing emits a `manual-test-pack.md` per D-002.

### `m365`

- **Output**: `platforms/m365/declarative-agent.json` (the manifest) plus `platforms/m365/instructions.md` for the instructions field.
- **Budget**: 8,000 characters on the instructions field, hard. Compilation fails if exceeded.
- **Persona**: strips by default (per SKL-008).
- **Tool / knowledge bindings**: rendered into the manifest's `actions[]` and `capabilities[]` arrays as platform-specific identifiers.
- **Schema version**: pinned per-skill in `skl/platforms/m365.yaml` via `schema_version: "1.7"` (or whichever version the skill targets). The pin is mandatory; the compiler emits `version: "<pinned-version>"` into the manifest. Bundled output schemas live in `_shared/schemas/platforms/m365/declarative-agent-manifest-<v>.json` with an `index.json` declaring supported / default / deprecated versions. See [SKL-009](../decisions/SKL-009-m365-schema-versioning.md) for the resolution rules and how new Microsoft schema releases reach the kit.

### `ms-cowork`

- **Output**: `platforms/ms-cowork/<name>.md`.
- **Budget**: none enforced; warn above 50K chars.
- **Persona**: strips by default (per SKL-008).
- **Implementation**: Skills-native consumer; compile is essentially a copy of the Anthropic Agent Skill folder. The earlier "delegates to the claude-cowork compiler" model was superseded by SKL-004's Skills-native compile path.

### `claude-code`

- **Output**: Anthropic Agent Skill folder at `platforms/claude-code/<name>/`, including `SKILL.md` with `skl:` frontmatter block stripped (per SKL-006) and a top-line provenance comment.
- **Budget**: none enforced; warn above 50K chars.
- **Persona**: strips by default (per SKL-008). Claude is the persona on this surface.
- **Knowledge sources**: rendered as file references in `references/` per Anthropic Skills convention.

### `claude-cowork`

- **Output**: Anthropic Agent Skill folder at `platforms/claude-cowork/<name>/`, same shape as `claude-code`.
- **Budget**: none enforced; warn above 50K chars.
- **Persona**: strips by default (per SKL-008).
- **Notes**: the canonical Cowork compiler; the `ms-cowork` compiler delegates here.

### `vscode`

Two emitted variants per SKL-007:

- **Skill variant** at `platforms/vscode/skill/<name>/` (an Anthropic Agent Skill folder). Same byte-stream as `claude-code` / `claude-cowork`. Persona strips by default (per SKL-008). Emitted whenever `vscode` is in `enabled_platforms` unless the sidecar declares `emit_skill: false`.
- **Custom Agent variant** at `platforms/vscode/agent/<name>.agent.md` (VS Code custom-agent format). Persona surfaces by default (per SKL-008). Emitted when `skl/platforms/vscode.yaml` sidecar exists. Frontmatter composition mapped in SKL-007.

`.chatmode.md` is never emitted (per SKL-007).

- **Budget**: none enforced; warn above 50K chars on either variant.

---

## Validators

`skl validate` runs eight families of check. They are listed in [`cli.md`](./cli.md) under `skl validate`; the per-family detail here is what compiler authors and SKILL.md authors need.

### Manifest

- Schema match against the manifest schema in this document and [`manifest.md`](./manifest.md).
- `skl_version` is parseable and matches the installed `skl`.
- `shared_kit.source` fetchable; `shared_kit.version` is an available tag.
- `enabled_platforms` is a subset of the six known platforms.

### Frontmatter

- Schema match against `_shared/schemas/skill.frontmatter.schema.json`.
- `name` is kebab-case, repo-unique, 3-5 words max.
- `display_name` is Title Case, 2-4 words.
- When `persona.nickname` or `persona.role` is set, the kebab `name`'s first segment matches it (lowercased) - per D-006.

### Body

- All canonical sections present and in canonical order: Identity, Tone, Capabilities, Knowledge Sources, Tools, Workflow, Output Format, Edge Cases, Examples, Validation Checklist.
- Each section is non-empty.
- Section anchors compilers depend on are present and unambiguous.

### Knowledge contracts

- Every knowledge ID referenced in frontmatter or body has a corresponding `<id>.contract.md` file.
- Every contract's frontmatter declares the platforms it binds to.
- Every contract's referenced files (if any) exist.

### Cross-references

- Cross-references within the skill resolve.
- Cross-references to other skills in the same repo resolve.
- Cross-references to skills in other repos resolve via `cross_repo_dependencies[]` (validation fetches the referenced SHA and confirms the skill exists).

### Shared-kit drift

- `_shared/.kit_version` matches `shared_kit.version` in the manifest.
- No file in `_shared/` (excluding `_shared/local/`) has been edited since sync; if so, list them.

### Values declarations

- Every `variables[]` entry in a SKILL.md either has a default in the SKILL.md frontmatter or is supplied by tier-1 / tier-2 / tier-3 values at deploy time.

### Compatibility

- The installed `skl` version is within `skl_version` range in the manifest.

---

## Adding a platform

A new platform compiler must:

1. Live under `src/skl/compilers/<platform_id>.py`.
2. Implement the compiler contract above.
3. Register in the platform registry (`src/skl/compilers/__init__.py`).
4. Document its output shape and budget in this file.
5. Add the platform ID to the known set referenced by `manifest.md`.
6. Provide at least one fixture in this repo's own `tests/`.

Backward-compatible additions are minor releases. Changing an existing compiler's output contract is a major release.

---

## See also

- [`cli.md`](./cli.md) - `skl compile`, `skl budget`, `skl validate`, `skl lint` reference.
- [`manifest.md`](./manifest.md) - `enabled_platforms` and persona surfacing.
- [`values-and-secrets.md`](./values-and-secrets.md) - why output is template-form.
- Parent project `ai-skills-lib/analysis/02_portable_skill_specification.md` - the SKILL.md format compilers parse.
- Parent project `ai-skills-lib/analysis/03_convenience_scripts_spec.md` §6 - the original compiler design.
