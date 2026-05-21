# SKL-004 - Master SKILL.md posture: Anthropic Skills base with `skl:` extensions and progressive sidecars

| Field | Value |
|-------|-------|
| **ID** | SKL-004 |
| **Date** | 20 May 2026 |
| **Status** | Final |
| **Owner** | Daniel Thomas |
| **Raised in** | [`docs/analysis/skills-spec.md`](../analysis/skills-spec.md) (18 May 2026) |
| **Resolves** | [Q-005](../open-questions.md#q-005---master-skillmd-posture-anthropic-skills-base-with-skl-extensions-or-fully-bespoke-superset) |
| **Partially answers** | [Q-006](../open-questions.md#q-006---frontmatter-namespacing-for-skl-added-fields) (namespacing default), [Q-008](../open-questions.md#q-008---vs-code-agent-skill-custom-agent-or-both) (where the `vscode:` opt-in lives) |

## Question

What is the source-of-truth file shape that authors write for one skill in a skill-host repo, given that the toolkit must compile to six platform targets with very different requirements?

The framing has shifted since `docs/spec/compilation.md` was written. As of May 2026, five of the six targets - claude.ai, Claude Code, Claude Cowork, MS Copilot Cowork, VS Code Agent Skills - accept the **same** Anthropic Agent Skills `SKILL.md` format directly. Only Copilot Studio, M365 declarative agents, and VS Code's `.agent.md` custom-agent surface need real per-platform compilation. The question is no longer "what neutral format compiles to six targets" but "what authoring shape inherits the open-standard portability while still carrying the metadata the three real-compile targets need."

Three postures were on the table:

- **A. Fully bespoke `skl` schema.** All top-level fields are `skl`-defined; we compile to all six surfaces, including the four where compile would otherwise be a copy.
- **B. Anthropic Skills only, no extensions.** The three real-compile targets derive what they need from `description` + body inspection; no declarative bindings, variables, persona, or per-platform overrides.
- **C. Anthropic Skills as base, `skl`-namespaced extensions for the superset.** SKILL.md is a valid Anthropic Skill; an `skl:` top-level frontmatter key carries the superset.

The pre-committed posture is "platform-neutral superset", which rules out **B**. The live decision is **A vs C**, with [`docs/analysis/skills-spec.md`](../analysis/skills-spec.md) §7 landing on **C**.

A secondary concern: under **C**, the `skl:` block can grow large for skills with rich per-platform bindings (the Casey example in the analysis already runs ~50 lines for two bindings). The single-file form risks becoming unwieldy. Should the master shape allow splitting into multiple files?

## Decision

Adopt posture **C**: SKILL.md is a valid Anthropic Agent Skill, with `skl`-namespaced extensions in the frontmatter for the superset metadata the non-Skills targets need.

Allow a **progressive-sidecar** layout to keep authored files readable as a skill grows:

1. **SKILL.md frontmatter** is the home for Anthropic-standard fields (`name`, `description`, and any other fields the open standard defines) plus an `skl:` block carrying **only cross-cutting essentials**: `schema_version`, `display_name`, `status`, `lifecycle`, `persona`, `enabled_platforms`, `variables[]`, and the platform-agnostic ID declarations for `knowledge[]` and `tools[]` (ID + contract reference only - no bindings).
2. **Per-platform sidecars** at `skl/platforms/<platform-id>.yaml` carry that platform's bindings (which connector / capability / action name to use for each declared knowledge or tool ID), its per-platform overrides (M365 `behavior_overrides`, VS Code `target` / `model` / `handoffs[]`, etc.), and any per-platform budget override. A sidecar exists **only when that platform is enabled and has something to declare**.
3. **The toolkit merges** SKILL.md frontmatter with any sidecars at validate / compile / deploy time. A skill that targets only Skills-native surfaces and uses no bindings has zero sidecars - identical authoring experience to a plain Anthropic Skill.

Specifically:

- `skl:` is the only `skl`-added top-level frontmatter key. Per-platform sub-blocks (`m365:`, `vscode:`, etc.) live in their sidecars under `skl/platforms/`, not inline at the top level of SKILL.md. This answers the inline-vs-namespaced part of Q-006: `skl:`-namespaced for inline cross-cutting content; sidecar files for platform-specific content.
- Knowledge and tool **IDs** live in `SKILL.md` `skl:` block; **bindings** live in the per-platform sidecars. The cross-cutting declaration says "this skill needs `case-study-library`"; the Copilot Studio sidecar says "the Copilot Studio name for `case-study-library` is `Case Studies Library`".
- The body of SKILL.md stays markdown prose. Required sections are enforced only where a downstream compiler needs an anchor; everything else is warned-if-missing rather than errored.
- Skills-native compile (claude-code, claude-cowork, ms-cowork, claude-ai uploads, VS Code Agent Skills) is a filesystem operation - copy the folder. The treatment of the `skl:` frontmatter block on Skills-native compile (strip vs pass through) is Q-007 and not decided here.

### Folder layout (concrete)

```
casey-case-studies/
├── SKILL.md                          # Anthropic-valid; minimal skl: block in frontmatter
├── scripts/                          # Anthropic convention
├── references/                       # Anthropic convention
├── assets/                           # Anthropic convention
├── tests/
│   └── test-cases.yaml               # skl convention; consumed by `skl test`
├── skl/                              # OPTIONAL - all sidecars live here
│   └── platforms/
│       ├── copilot-studio.yaml       # only when enabled & non-trivial
│       ├── m365.yaml
│       └── vscode.yaml
└── platforms/                        # compiled artefacts (D-001), template-form (D-007)
    └── ...
```

### Worked example (frontmatter only)

```yaml
---
# === Anthropic Skills base ===
name: casey-case-studies                  # <=64, kebab, no reserved words
description: |                            # <=1000 chars (M365 cap is tighter than Anthropic's 1024)
  Retrieve and synthesise consulting case studies from the firm's SharePoint library.
  Use PROACTIVELY when the user asks about past engagements, references, win themes,
  or capability statements.

# === skl-namespaced extensions ===
skl:
  schema_version: 1
  display_name: Casey - Case Studies
  status: active
  lifecycle: business_development
  persona: { nickname: Casey, role: Case Studies Specialist }
  enabled_platforms: [copilot-studio, m365, claude-code, claude-cowork]
  variables:
    - { name: consulting_company, description: The firm running the skill, required: true }
    - { name: case_study_library_path, description: SharePoint path to the library, required: true }
  knowledge:
    - id: case-study-library
      contract: knowledge/case-studies.contract.md
  tools:
    - id: web_fetch
---
```

```yaml
# skl/platforms/copilot-studio.yaml
bindings:
  knowledge: { case-study-library: "Case Studies Library" }
  tools:     { web_fetch: "Web Fetch" }
budget: 7500
```

```yaml
# skl/platforms/m365.yaml
schema_version: "1.7"
bindings:
  knowledge:
    case-study-library:
      capability: OneDriveAndSharePoint
      items_by_url: ["{{variables.case_study_library_path}}"]
  tools:
    web_fetch: { action: web-fetch-plugin }
behavior_overrides: { default_response_mode: Auto }
conversation_starters:
  - "Find case studies for a banking client"
  - "What have we done in healthcare consulting?"
disclaimer: { text: "Case studies summarised by AI; verify before use in proposals." }
```

## Rationale

**Why C over A.** Five of the six targets accept the Anthropic Skills format directly. Authoring a master file that is itself a valid Anthropic Skill makes the compile for those four targets a filesystem operation rather than a code path - a smaller surface of `skl` to build and maintain. Posture A throws away that affordance to gain a cleaner internal model; the cost is too high for what is a transient internal-cleanliness win.

**Why progressive sidecars over a single fat file.** Inlining all per-platform bindings under `skl:` produces a hostile frontmatter block once a skill targets more than two real-compile platforms. Per-platform sidecars keep each file readable, give clean per-platform diffs, and make enabling a new platform an additive operation (one new file, no edits to SKILL.md). Crucially, the simple case stays simple: a Claude-Code-only skill has no sidecars and reads as a plain Anthropic Skill.

**Why `skl/platforms/<id>.yaml` and not flat `SKILL.<id>.yaml` at the top level.** The folder convention keeps the top of the skill folder Anthropic-shaped (SKILL.md + scripts/ + references/ + assets/), so consumers that know nothing about `skl` see what they expect. `skl/` clearly demarcates toolkit-managed config and scales to hold further sidecars in future (e.g. `skl/contracts.yaml` if knowledge / tool ID lists grow beyond what feels right in frontmatter - not promised here, but the layout leaves room).

**Why IDs in SKILL.md and bindings in sidecars.** This split mirrors the conceptual layering: SKILL.md describes what the skill *needs* in the abstract (a knowledge source, a tool); the sidecars describe *how that lands* on each surface. A reader can answer "what does this skill depend on?" from SKILL.md alone, without opening every sidecar. Adding a binding for a new platform is purely additive.

**Why merge instead of overlay.** The toolkit reads SKILL.md frontmatter and any sidecars and produces a single resolved skill model. Sidecars supply per-platform bindings keyed by IDs declared in the frontmatter; there is no conflict surface that needs precedence rules. If a future change needs sidecars to override cross-cutting fields, that can be added with a precedence policy then.

**Why Anthropic ignores `skl:` safely.** The canonical `anthropics/skills/skill-creator/SKILL.md` includes a `compatibility:` field that Anthropic's loader does not consume, and `description` is the only frontmatter field Claude reads to decide whether to load a skill. Unknown top-level keys (`skl:`, `version:`, `author:`) are ignored. The risk is a future Anthropic field colliding with `skl:`; vendor-prefixed names are conventionally avoided in YAML specs.

## What this constrains in `skl`

- `_shared/schemas/skill.frontmatter.schema.json` defines the `skl:` block shape: `schema_version` (int), `display_name` (string), `status` (enum), `lifecycle` (string), `persona` (object), `enabled_platforms` (array of platform IDs), `variables` (array of `{name, description, required, default?}`), `knowledge` (array of `{id, contract}`), `tools` (array of `{id}`). Platform-specific blocks are **not** valid at the top level of `skl:`.
- A per-sidecar schema set at `_shared/schemas/platforms/<platform-id>.schema.json`, one per platform. The Copilot Studio schema allows `bindings` and `budget`; the M365 schema allows `bindings`, `schema_version`, `behavior_overrides`, `conversation_starters`, `disclaimer`, `actions`, `editorial_answers`, `worker_agents`, `user_overrides`; the VS Code schema allows `bindings`, `target`, `model`, `tools`, `agents`, `handoffs`, `hooks`.
- `skl init` repo-scoped form scaffolds `SKILL.md` only by default. A future `skl add-platform <id>` (or equivalent flag on `init`) creates the matching sidecar with sensible defaults.
- `skl validate`:
  - Validates SKILL.md frontmatter against the master schema.
  - For each file under `skl/platforms/<id>.yaml`, validates against the corresponding platform schema.
  - Cross-checks that every `id` referenced in a sidecar's `bindings.knowledge` / `bindings.tools` is declared in the master `skl.knowledge[]` / `skl.tools[]`. Unknown IDs are errors. Declared IDs missing a binding for an `enabled_platforms` entry are warnings.
  - Warns if `enabled_platforms` includes a platform with no sidecar **and** the skill declares any bindings (likely an omission); silent otherwise.
- `skl compile <platform>` reads SKILL.md plus the corresponding sidecar (if present) and emits the compiled artefact. The merge happens in-memory; the compiler never writes a combined file back to source.
- Body sections in SKILL.md follow the recommended structure in [`docs/analysis/skills-spec.md`](../analysis/skills-spec.md) §7.4 (13 sections, with required vs optional flagged). The exact required set is settled separately - this decision constrains the frontmatter and folder layout, not the body lint policy.

## Open follow-ups

This decision opens or partially-answers several downstream questions tracked separately:

- **Q-006** (frontmatter namespacing) is partially answered: `skl:` is the single top-level namespace for cross-cutting inline content; per-platform content lives in sidecars. The remaining sub-question - whether platform IDs (`m365`, `vscode`) might ever appear at the top level - is left open in case a future case warrants it.
- **Q-007** (strip vs pass-through `skl:` on Skills-native compile) is not decided here and still needs a separate record.
- **Q-008** (VS Code Agent Skill vs Custom Agent variant) is partially answered: the opt-in signal is "does `skl/platforms/vscode.yaml` exist?". Whether to emit both variants by default or only on opt-in still needs a call.
- **Q-009** (persona stripping per target) is unchanged; persona lives in `skl.persona` and stripping is a compiler concern.
- **Q-010** (variables location) is answered: `skl.variables[]` in SKILL.md frontmatter; defaults inline; substitution stays at deploy time per D-007.
- **Q-011** (handoff modelling) is deferred to v0.2+ as the analysis recommends.
- **Q-012** (M365 schema versioning) is unaffected by this decision; the `schema_version` in `skl/platforms/m365.yaml` is the per-skill pin.

## See also

- [`docs/analysis/skills-spec.md`](../analysis/skills-spec.md) - the full pre-spec analysis that grounds this decision.
- [`docs/spec/compilation.md`](../spec/compilation.md) - existing per-platform compiler spec, to be revised in light of this decision.
- [`docs/spec/manifest.md`](../spec/manifest.md) - `skill-repo.yaml` schema (unaffected).
- [`D-001`](https://github.com/danielithomas/ai-skills-lib/blob/main/analysis/06_decision_log.md) - compiled `platforms/` artefacts are committed (this decision preserves that).
- [`D-006`](https://github.com/danielithomas/ai-skills-lib/blob/main/analysis/06_decision_log.md) - per-platform persona surfacing defaults.
- [`D-007`](./D-007-three-tier-values.md) - variables and deploy-time substitution.
- [`D-011`](./D-011-shared-kit-fetched.md) - `_shared/schemas/` is where the codified schemas land.
