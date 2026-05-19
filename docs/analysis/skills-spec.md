---
status: analysis / pre-spec
date: 18 May 2026
informs: docs/spec/compilation.md, docs/spec/cli.md (`skl init` repo-scoped form), future docs/spec/skill.md
raises: Q-005 through Q-012 in docs/open-questions.md
---

# Skills spec analysis: how should a master SKILL.md be structured?

This is the pre-spec analysis that informs the SKILL.md authoring model `skl` will scaffold and compile. The current `docs/spec/compilation.md` names a ten-section canonical body and references an `_shared/schemas/skill.frontmatter.schema.json` that does not yet exist. Before we lock either, we need to re-validate the proposed shape against (a) what each of the six target platforms actually accepts today, (b) what the user has already evolved by hand in `prompt_library/`, and (c) the wider ecosystem that has formed around the literal filename `SKILL.md` since late 2025.

The finding that re-frames everything: **Anthropic's Agent Skills format (`SKILL.md` + folder) is becoming a cross-platform open standard.** As of May 2026 it is accepted natively by claude.ai, Claude Code, Claude Cowork, Microsoft Copilot Cowork, VS Code's GitHub Copilot, and Microsoft Foundry; only Copilot Studio, M365 declarative agents, and VS Code's custom-agent (`.agent.md`) surface still need real per-platform compilation. The six-target compilation problem is closer to a three-target compilation problem with one well-defined intersection.

---

## 1. Scope

In scope:
- The shape of the **master** SKILL.md authored in a skill-host repo: frontmatter schema, body sections, folder layout, file naming.
- How that master shape compiles to (or is consumed directly by) each of the six platform targets named in `docs/spec/compilation.md`: `copilot-studio`, `m365`, `ms-cowork`, `claude-code`, `claude-cowork`, `vscode`.
- The treatment of persona, variables, tool bindings, knowledge sources, and character budgets across those targets.
- The trade-off between strict Anthropic Skills compatibility (so we inherit cross-platform portability for free) and a richer `skl`-managed superset (so we can carry the metadata the non-Skills targets need).

Out of scope (here):
- The exact JSON Schema for the master frontmatter; that lands in a follow-up decision (`SKL-NNN`) and codifies what this doc recommends.
- The per-platform compiler implementation details; covered in `docs/spec/compilation.md` once the master shape is settled.
- Values / secrets resolution (D-007 / D-008); the analysis assumes those mechanisms exist, and only flags where the master frontmatter must declare what they substitute.
- Migrating the legacy `prompt_library/` agents; covered separately by `skl migrate`.

---

## 2. Methodology and sources

The findings draw on three classes of evidence, gathered between 17 and 18 May 2026:

1. **Legacy authored material.** Six Copilot Studio agent specs and the Claude / Copilot / generic templates under `/home/dthomas/dev/prompt_library/`, mined by a sub-agent to extract the conventions the user has converged on by hand without spec guidance.
2. **Microsoft Learn primary sources.** Pages for Copilot Studio authoring instructions, agent quotas, M365 declarative-agent manifest v1.7 / v1.3, and Copilot Cowork overview; all fetched with verifiable `ms.date` / `updated_at` metadata in March-May 2026.
3. **Anthropic and Microsoft web sources.** docs.claude.com, platform.claude.com, code.claude.com, code.visualstudio.com, learn.microsoft.com, Anthropic engineering blog, Microsoft 365 blog. URLs and dates listed in the bibliography (§10).

Constraint flags worth noting:
- The Anthropic Agent Skills spec is iterating; field-level claims here are correct as of 18 May 2026 and should be re-verified before they land in a public spec.
- VS Code is mid-rename from `.chatmode.md` to `.agent.md`; legacy format is still accepted but no longer the primary path. The custom-agent frontmatter has expanded (handoffs, agents, hooks).
- M365 declarative-agent manifest is at v1.7 (page updated 14 May 2026); the user's existing `docs/spec/compilation.md` predates several capability surfaces (editorial answers, worker agents, behavior overrides).
- The parent project's analysis (`ai-skills-lib/analysis/02_portable_skill_specification.md`) is not reachable locally; this analysis is a re-derivation rather than a continuation.

---

## 3. Headline finding: SKILL.md is becoming a cross-platform open standard

The most consequential update to the spec's worldview is this. When `docs/spec/compilation.md` was written, the assumption was that each of the six platforms needed a bespoke compiler producing a bespoke artefact. That was true in 2025. As of May 2026 it is no longer true: five of the six surfaces accept the **same** Anthropic Agent Skills format directly, and the sixth (M365 declarative agents) consumes it indirectly via its `instructions` string and `actions` array.

| Surface | Accepts Anthropic SKILL.md directly? | Install location |
|---|---|---|
| Claude API | Yes (uploaded via Skills API `/v1/skills`) | Workspace-wide |
| Claude Code | Yes (Custom Skills) | `~/.claude/skills/<name>/SKILL.md` or `.claude/skills/<name>/SKILL.md` |
| claude.ai | Yes (uploaded via Settings > Features as zip) | Per-user |
| Claude Cowork | Yes (skills bundled as Skills) | Per Anthropic Cowork product docs |
| Microsoft Copilot Cowork | Yes | `~/Documents/Cowork/skills/<name>/SKILL.md` in OneDrive, auto-discovered, 50-skill cap |
| VS Code (GitHub Copilot) | Yes (Agent Skills are first-class) | `.github/skills/`, `.claude/skills/`, `.agents/skills/`, `~/.copilot/skills/`, etc. |
| Microsoft Foundry | Yes (inherits Claude API behaviour) | Skills API |
| M365 declarative agents | No, distinct manifest | App package |
| Copilot Studio | No, free-text 8K instructions field | Per agent, in Dataverse |

This re-frames the toolkit. The default behaviour for the four Anthropic-native targets and Cowork is **copy, not compile**. The remaining real compilation targets are:

- **Copilot Studio** - a single 8,000-character free-text instructions field plus UI-bound knowledge / tools / topics.
- **M365 declarative agents** - a JSON manifest (v1.7) with an inline `instructions` string field (also capped at 8,000 chars) plus rich `capabilities`, `actions`, `behavior_overrides`, `editorial_answers`, `worker_agents` surfaces.
- **VS Code custom agents (`.agent.md`)** - a richer frontmatter (`handoffs`, `agents`, `tools`, `model`, `target`, `mcp-servers`, `hooks`) and body of markdown prose; an alternative to shipping the same skill as an Agent Skill.

This finding is recoverable - if the open-standard story regresses (e.g. Anthropic forks the spec, or Microsoft's "build on Anthropic tech" claim about Cowork turns out to mask a divergence) we fall back to per-platform compilation. But the architecture should be designed for the convergence, not against it.

---

## 4. Platform-by-platform format summary

### 4.1 Anthropic Agent Skills (`SKILL.md`)

The de facto standard. Treat as the gravity well around which the master shape orbits.

**Folder structure:**

```
skill-name/
├── SKILL.md            (required)
├── scripts/            (optional - executable code, run via bash, code never enters context)
├── references/         (optional - .md files loaded only when explicitly referenced)
└── assets/             (optional - templates, schemas, fixtures)
```

**Required frontmatter:**

| Field | Type | Constraint |
|---|---|---|
| `name` | string | Max 64 chars, kebab-case (`^[a-z0-9-]+$`), cannot contain XML tags, cannot contain reserved words `anthropic` or `claude` |
| `description` | string | Max 1024 chars, non-empty, no XML tags. **Primary trigger** - this is what Claude reads to decide whether to load the skill |

**Optional / extended frontmatter (observed across the canonical examples, the VS Code consumer, and the broader ecosystem):**

| Field | Type | Source | Meaning |
|---|---|---|---|
| `compatibility` | object | anthropics/skills `skill-creator` canonical example | Required tools / dependencies |
| `version` | string | community spec, not Anthropic-mandated | Skill version |
| `author` | string | community spec | Author handle / email |
| `license` | string | community spec | SPDX identifier |
| `allowed-tools` | list | community spec | Tool allow-list |
| `argument-hint` | string | VS Code extension | Hint shown in chat input for slash-command invocation |
| `user-invocable` | bool | VS Code extension | Whether the skill appears in the dropdown (default true) |
| `disable-model-invocation` | bool | VS Code extension | Prevent the model from invoking this skill autonomously |
| `context: fork` | enum | VS Code experimental | Run in dedicated subagent context |

**Body:** loose. The canonical `skill-creator` example uses `# Title`, `## Overview`, then a sequence of working sections (`## Communicating with the user`, `## Creating a skill`, `## Running and evaluating test cases`, `## Improving the skill`, and a couple of platform-specific sections including a literal `## Cowork-Specific Instructions` block). There is no required canonical order. Anthropic's style guidance favours imperative tone, theory-of-mind explanations over rigid MUSTs, and progressive disclosure (keep SKILL.md body under ~5K tokens, push detail into `references/`).

**Progressive disclosure (the architectural commitment):**

| Level | When loaded | Token cost | Content |
|---|---|---|---|
| 1: Metadata | Always at startup | ~100 tokens per skill | `name` + `description` |
| 2: Instructions | When skill is triggered | Under 5K tokens | SKILL.md body |
| 3+: Resources | As needed, via bash | Effectively unlimited | `scripts/`, `references/`, `assets/` |

**Loading mechanism:** Claude discovers skills from the filesystem at session start, reads SKILL.md body via bash when the user request matches the description, and reads bundled resources via bash when SKILL.md references them.

**Constraints worth flagging for the master shape:**
- The 1024-char `description` limit is binding. Authors should treat it as a load-bearing piece of advertising copy, not a free-text summary.
- The body is uncapped but should target ~5K tokens for performance. This is similar in order of magnitude to Copilot Studio's 8K char hard limit.
- The reserved-word rule means a skill cannot be named `claude-anything` or `anthropic-anything`; affects naming policy.

### 4.2 Claude Code subagents (`.claude/agents/*.md`)

A **separate** Claude Code feature from Skills, not the same thing. Subagents are scoped to a single Claude Code session and consume their own context window; Skills are reusable, on-demand procedural knowledge.

| Field | Required | Type | Meaning |
|---|---|---|---|
| `name` | Yes | string | Subagent identifier |
| `description` | Yes | string | When this subagent should be invoked. Idioms `use PROACTIVELY` and `MUST BE USED` documented to encourage delegation |
| `tools` | No | comma-separated string | Tool allow-list; omit to inherit all main-thread tools (including MCP) |
| `model` | No | string | Model id (e.g. `haiku` for cheaper/faster work) |

Body is markdown prose that becomes the subagent's system prompt. No required structure. File locations: `.claude/agents/` (project) or `~/.claude/agents/` (user). No documented character limit.

Subagents and Skills can coexist in the same Claude Code workspace. They are siblings under `.claude/`, not alternatives.

### 4.3 Claude Cowork (Anthropic, desktop, Jan 2026)

Anthropic's desktop agent that operates on local files / folders / applications. Bundles **skills, connectors, and sub-agents** as the unit of capability. As of May 2026 the public documentation does not enumerate a Cowork-specific file format separate from Anthropic Agent Skills; the model is that you author a Skill and ship it as part of a Cowork bundle. Treat as a SKILL.md consumer; flag for re-verification.

### 4.4 Microsoft Copilot Cowork (Microsoft, M365 Frontier, Mar 2026)

Built on Anthropic's tech, accepts SKILL.md **directly**. Custom skills live in OneDrive under `~/Documents/Cowork/skills/<skill-name>/SKILL.md`. Auto-discovered at start of each conversation. Cap: 50 custom skills per user. Plugins (M365 App Store, including admin-deployed) layer additional skills + connectors. Available in browser at `m365.cloud.microsoft`, M365 Copilot desktop, and mobile.

For our purposes: same format as Anthropic Skills. Compile target reduces to "package the skill folder and place it in the right OneDrive path".

### 4.5 Microsoft Copilot Studio agent instructions

A single free-text `Instructions` field on each custom agent. Hard limit: **8,000 characters** (confirmed in `requirements-quotas`, updated 13 May 2026). Tools, knowledge sources, topics, and sub-agents are bound in the Copilot Studio UI separately and referenced from instructions via `/` autocomplete; they cannot be added inline from the instructions text.

No required section structure. Microsoft explicitly warns against instructions that "modify, override or interfere with the system-defined citation format" - phrases like "citation" or "reference" can cause the orchestrator to drop grounded outputs. The "T-C-R" (Tone-Capabilities-Rules) framework the user follows is **community convention**, not Microsoft-mandated.

Other limits on the same Dataverse env: 100 skills per agent, 1,000 topics per agent, 200 trigger phrases per topic, 8,000 messages-per-minute quota.

### 4.6 Microsoft 365 declarative agents

JSON manifest (`declarative-agent.json`) referenced from the M365 app manifest. **Current schema is v1.7**, updated 14 May 2026.

Top-level manifest properties relevant to the master shape:

| Property | Type | Required | Constraint |
|---|---|---|---|
| `version` | string | Yes | `v1.7` |
| `name` | string | Yes | Localisable, &le; 100 chars |
| `description` | string | Yes | Localisable, &le; 1,000 chars |
| `instructions` | string | Yes | **&le; 8,000 chars** - the system prompt |
| `capabilities` | array | No | One of each type max (see below) |
| `conversation_starters` | array | No | Localisable, max 12 |
| `actions` | array | No | 1-10 plugin refs |
| `behavior_overrides` | object | No | `suggestions.disabled`, `default_response_mode` (`Auto` / `Quick response` / `Think deeper`) |
| `disclaimer` | object | No | `text` &le; 500 chars |
| `editorial_answers` | object | No | URL or up to 300 Q/A pairs |
| `worker_agents` | array | No | Sub-agent refs (preview) |
| `user_overrides` | array | No | JSONPath toggles |

Capability objects (declared inside `capabilities[]`): `WebSearch`, `OneDriveAndSharePoint`, `GraphConnectors`, `GraphicArt`, `CodeInterpreter`, `Dataverse`, `TeamsMessages`, `Email`, `People`, `ScenarioModels`, `Meetings`, `EmbeddedKnowledge`.

Bundled in an M365 app package (zip). Distributed per-tenant, per-user, or via the Microsoft 365 marketplace.

### 4.7 VS Code custom agents (`.agent.md`)

Active migration from `.chatmode.md`. Same functional model, renamed. Frontmatter has expanded; legacy `.chatmode.md` still accepted.

| Field | Required | Type | Meaning |
|---|---|---|---|
| `description` | No | string | Shown as placeholder text in chat-mode picker |
| `name` | No | string | Defaults to filename |
| `argument-hint` | No | string | Hint in chat input |
| `tools` | No | array | Tool / tool-set names; supports `<server>/*` for MCP |
| `agents` | No | array | Sub-agent allow-list; `*` for all, `[]` to disable |
| `model` | No | string or array | Single model or prioritised list |
| `user-invocable` | No | bool | Default true |
| `disable-model-invocation` | No | bool | Default false |
| `target` | No | enum | `vscode` or `github-copilot` |
| `mcp-servers` | No | array | MCP server config for github-copilot targets |
| `handoffs` | No | array | Sequential workflow transitions (each: `label`, `agent`, `prompt`, `send?`, `model?`) |
| `hooks` | No | object | Agent-scoped hook commands (preview) |
| `infer` | - | bool | **Deprecated**, replaced by `user-invocable` + `disable-model-invocation` |

Locations: `.github/agents/` (primary), `.claude/agents/` (also auto-discovered, supports Claude-format comma-separated tools), `~/.copilot/agents/`, custom via `chat.agentFilesLocations`. Body is markdown prose used as system prompt. No documented character limit.

VS Code also natively consumes Anthropic Agent Skills at `.github/skills/`, `.claude/skills/`, `.agents/skills/`, etc., distinct from custom agents. The two formats coexist:

| Artefact | Purpose | Portability |
|---|---|---|
| Agent Skill (`SKILL.md`) | On-demand specialised capability | Open standard, cross-tool |
| Custom Agent (`.agent.md`) | Persistent persona + tool restrictions + handoffs | VS Code-specific (and Claude Code via `.claude/agents/`) |
| Custom Instructions (`*.instructions.md`) | Coding standards, auto-attached by glob | VS Code / github.com only |
| Prompt File (`*.prompt.md`) | Reusable slash command | VS Code-specific |
| `.github/copilot-instructions.md` | Always-attached workspace defaults | VS Code / github.com only |

---

## 5. What the user has already evolved by hand

Mining the legacy `prompt_library/` confirms two things that should constrain the master shape, and surfaces one tension worth resolving:

**Confirmed convergent practice:**
- Every Copilot Studio agent leads with **Identity** ("You are [Name], a [role]..."), then varies. Identity-first is universal; the rest is platform-driven.
- Authors target ~5,500 - 6,500 chars on Copilot Studio, leaving headroom against the 8K cap. The hard limit shapes the writing.
- Two recurring patterns the existing `compilation.md` does not name: **explicit "What You CAN / CANNOT Do" capability lists**, and **verbatim response templates** as guardrails ("If the user asks about X, respond with the following exact text..."). Both appear across multiple agents.
- Australian English is explicit in several agent specs; aligns with `CLAUDE.md`'s house style.

**Tension surfaced:**
- The Copilot Studio template assumes escalation-to-human as a core pattern (dedicated `## ESCALATION & HANDOFF` section). The actual library agents are search / lookup / validation systems that do not escalate; they return "no results" or "non-compliant" instead. The template is wrong about its own users.

**Implication for the master shape:**
- Universal sections (always required): Identity, Capabilities (CAN / CANNOT lists), Knowledge Sources, Workflow, Examples, Edge Cases.
- Often-but-not-always: Tone (some agents inline it into Identity; some give it its own section), Response Templates (only for agents with rigid output requirements), Validation Checklist (only for agents that produce reviewable artefacts).
- Almost never used in practice: Escalation, Privacy / Security (assumed handled out-of-band), Continuous Improvement (aspirational).

The existing `compilation.md` ten-section canon is broadly right but mixes "always required" with "often optional". The master shape should distinguish them.

---

## 6. Cross-platform capability matrix

### 6.1 Surface support for proposed master features

| Master feature | Anthropic Skills | Claude Code subagent | Claude Cowork | MS Copilot Cowork | Copilot Studio | M365 declarative | VS Code custom agent |
|---|---|---|---|---|---|---|---|
| Skill name (kebab) | `name` &le;64 | `name` | inherits Skills | inherits Skills | agent display name | `name` &le;100 | `name`, defaults to filename |
| Trigger description | `description` &le;1024 | `description` | inherits | inherits | description (sub-agent surface) | `description` &le;1,000 | `description` (placeholder text) |
| System-prompt body | SKILL.md body (loose, target &lt;5K tok) | body (uncapped) | inherits | inherits | `Instructions` field, **&le;8,000 chars hard** | `instructions` field, **&le;8,000 chars hard** | body (uncapped) |
| Persona / identity | not first-class | not first-class | inherits | inherits | inline in instructions | inline in instructions | inline in body |
| Tool bindings | `allowed-tools` (community) | `tools` (CSV) | inherits | inherits | UI-bound, `/`-referenced | `actions[]` (plugin refs 1-10) | `tools[]` (incl. `server/*` MCP) |
| Knowledge sources | bash-loaded `references/` | inherits | inherits | inherits | UI-bound Knowledge Sources | `capabilities[]` (typed) | references via `*.instructions.md` glob |
| Conversation starters | not modelled | not modelled | inherits | inherits | UI surface, separate | `conversation_starters[]` max 12 | not modelled |
| Sub-agents / handoffs | not modelled | not modelled | bundled | bundled | sub-agent surface | `worker_agents[]` preview | `agents[]` + `handoffs[]` |
| Model pinning | not modelled | `model` | not modelled | not modelled | not user-controlled | `behavior_overrides.default_response_mode` (Quick / Auto / Think deeper) | `model` string or list |
| Response-format guardrails | freeform body | freeform body | inherits | inherits | freeform inside 8K | `behavior_overrides`, `disclaimer.text` &le;500 | freeform body |
| Editorial / FAQ pairs | not modelled | not modelled | not modelled | not modelled | Topics surface | `editorial_answers[]` up to 300 | not modelled |
| Auto-discovery | filesystem | filesystem | filesystem | OneDrive auto-scan, 50-cap | UI registration | M365 app package | filesystem |
| Char/token budget | ~5K tokens body target | uncapped | inherits | inherits | **8K chars hard** | **8K chars hard** | uncapped |

### 6.2 Intersection (required core for any master skill)

These five fields / sections must exist for every master skill if it is to be compilable to all six targets:

1. **`name`** - kebab, &le; 64 chars (tightest constraint wins; satisfies both Skills' 64 and M365's 100).
2. **`description`** - &le; 1,000 chars (M365's 1,000 is tighter than Skills' 1,024; if we want both to round-trip, &le;1,000).
3. **Identity / persona block** - inline in body, not a frontmatter field. Required first paragraph for Copilot Studio / M365 compile. Optional but harmless for Skills targets.
4. **Capabilities** - "what you can do / cannot do" lists. Required substance for Copilot Studio (counts against the 8K budget; brevity matters). Convertible to a single tight paragraph for `description` enrichment too.
5. **Workflow** - the step-by-step procedure for the primary task. Universal. The character budget for Copilot Studio constrains it more than Skills targets.

### 6.3 Union (superset surface the master must declare somewhere)

These need a home in the master frontmatter or body so per-platform compilers can find them. They are not universally consumed.

- **Tool bindings** with per-platform identifiers (Copilot Studio connector names, MCP server names, Anthropic `allowed-tools`, M365 plugin refs).
- **Knowledge source bindings** with per-platform identifiers (SharePoint sites/lists, GraphConnector IDs, Anthropic `references/` paths, VS Code instructions globs).
- **Conversation starters** (M365 only) - up to 12 strings.
- **Editorial Q/A pairs** (M365 only) - up to 300.
- **Handoffs / worker agents** (VS Code, M365 preview).
- **Model preference** (Claude Code subagent, VS Code custom agent).
- **Disclaimer text** (M365) - &le; 500 chars.
- **Variables** (D-007) - declared per-skill, substituted at deploy. Not modelled by any platform; pure `skl` concern.

---

## 7. Proposed master SKILL.md structure

### 7.1 Posture

The user chose **platform-neutral superset** as the master posture. This analysis lands on a specific shape for that posture: **Anthropic Skills as the base, with `skl`-namespaced extensions for the superset surface.** Rationale:

- **Five of the six targets already accept the Anthropic Skills format directly.** A skill authored as a plain Anthropic Skill is automatically portable to claude.ai, Claude Code (as a Custom Skill), Claude Cowork, MS Copilot Cowork, and VS Code (as an Agent Skill).
- The remaining three real compile targets (Copilot Studio, M365 declarative, VS Code custom agent) all need a subset of the master's content. They consume a transformation, not a different source.
- An `skl:` namespace under the YAML frontmatter (or a single top-level `skl:` key whose value is an object) carries everything the non-Skills targets need without polluting the Anthropic-standard fields. Anthropic's loader ignores unknown frontmatter keys (per `compatibility` being accepted in the canonical `skill-creator` example).
- The body stays markdown prose with **recommended** canonical sections, not strictly required - mirroring Anthropic's posture, which favours theory-of-mind over rigid MUSTs. `skl validate` enforces structure only where a downstream compiler needs an anchor.

### 7.2 Proposed folder layout

```
skills/<skill-name>/
├── SKILL.md                          # Master; valid Anthropic Skill on its own
├── scripts/                          # Optional, Anthropic convention, run via bash
├── references/                       # Optional, Anthropic convention, loaded on reference
├── assets/                           # Optional, fixtures / templates / schemas
├── tests/
│   └── test-cases.yaml               # skl convention, consumed by `skl test`
└── platforms/                        # Compiled artefacts (D-001), template-form (D-007)
    ├── copilot-studio/instructions.md
    ├── m365/declarative-agent.json
    ├── m365/instructions.md
    ├── ms-cowork/                    # zero-touch: SKILL.md is the artefact (copy or symlink)
    ├── claude-code/                  # zero-touch
    ├── claude-cowork/                # zero-touch
    └── vscode/
        ├── skill/SKILL.md            # Agent Skill variant (preferred)
        └── agent/<name>.agent.md     # Custom Agent variant (if frontmatter declares it)
```

Note the `platforms/` directory still exists for non-Anthropic-Skills targets (per D-001's commitment to committed, directly-consumable artefacts). For the five Skills-native targets the `platforms/<id>/` content is either (a) a literal copy of the SKILL.md folder, (b) a thin packaging wrapper (e.g. zip for claude.ai upload), or (c) absent if installation is just "point at the source folder". See §8 for per-platform detail.

### 7.3 Proposed frontmatter

```yaml
---
# === Anthropic Skills base (compatible with the open standard) ===
name: casey-case-studies                            # kebab, <=64, no reserved words
description: |                                       # <=1000 chars (tightened from 1024 for M365 compat)
  Retrieve and synthesise consulting case studies from the firm's SharePoint library.
  Use PROACTIVELY when the user asks about past engagements, references, win themes,
  or capability statements. Returns case-study summaries with attribution.

# === skl-namespaced extensions (ignored by non-skl consumers) ===
skl:
  schema_version: 1
  display_name: Casey - Case Studies                # Title Case, 2-4 words
  status: active                                    # active | deprecated
  lifecycle: business_development                   # phase, drives SKILLS_INDEX grouping
  persona:                                          # surfaces are platform-driven (D-006)
    nickname: Casey
    role: Case Studies Specialist
  enabled_platforms:                                # subset of repo's enabled_platforms
    - copilot-studio
    - m365
    - claude-code
    - claude-cowork
  variables:                                        # D-007 declarations
    - name: consulting_company
      description: The firm running the skill
      required: true
    - name: case_study_library_path
      description: SharePoint or filesystem path to the library
      required: true
  knowledge:                                        # platform-agnostic refs + bindings
    - id: case-study-library
      contract: knowledge/case-studies.contract.md
      bindings:
        copilot-studio: "Case Studies Library"      # SharePoint Knowledge Source name
        m365: { capability: OneDriveAndSharePoint, items_by_url: ["{{variables.case_study_library_path}}"] }
        anthropic-skills: references/case-studies/  # bash-loaded directory
  tools:                                            # platform-agnostic IDs + bindings
    - id: web_fetch
      bindings:
        copilot-studio: "Web Fetch"                 # Copilot Studio connector name
        claude-code: WebFetch                       # tool id in subagent `tools` CSV
        vscode: web/fetch
  budgets:                                          # optional per-skill overrides
    copilot-studio: 7500                            # tighter than the 8000 hard limit
  conversation_starters:                            # M365-only; harmless elsewhere
    - "Find case studies for a banking client"
    - "What have we done in healthcare consulting?"
  m365:                                             # platform-specific block; opt-in
    behavior_overrides:
      default_response_mode: Auto
    disclaimer:
      text: "Case studies summarised by AI; verify before use in proposals."
  vscode:                                           # platform-specific block; opt-in
    target: vscode
    tools: [codebase, search/usages]
    model: ["Claude Sonnet 4.6", "GPT-5.2 (copilot)"]
---
```

Notes on the shape:
- **Base layer is a valid Anthropic Skill.** A consumer that knows nothing about `skl` (claude.ai, Cowork) reads `name` and `description`, ignores `skl:`, and works.
- **`skl:` is the only `skl`-added top-level key.** Avoids colliding with future Anthropic fields. The `m365:` and `vscode:` blocks live inside `skl:` (not shown above for brevity; could also be top-level). Open question: see Q-006.
- **Persona is `skl:`-scoped, not a top-level Anthropic field.** Skills format does not model persona; we surface it during compile to Copilot Studio / M365 / VS Code as inline body text, and strip it for Claude-family targets where Claude itself is the persona.
- **Knowledge and tools are declared once with per-platform bindings.** Replaces the existing spec's implicit `knowledge.id` and `tools.id` tokens with explicit binding maps. The compiler reads bindings to produce platform-specific references.
- **Variables stay declarative.** Defaults / tier-1 values can live alongside; tier-2 / tier-3 resolution remains as D-007.
- **Conversation starters and editorial Q/A** live in the frontmatter and are silently dropped by compilers whose target does not support them. Authors are not forced to know that M365 supports starters and Copilot Studio uses a different surface.

### 7.4 Proposed body sections

Recommended order, with required-vs-optional flags. `skl validate` requires the **Required** ones; the others are warned-if-missing rather than errored.

| # | Section | Required | Notes |
|---|---|---|---|
| 1 | `# {{display_name}}` | Yes | H1, mirrors `skl.display_name` |
| 2 | `## Identity` | Yes for Copilot Studio / M365 / VS Code | Stripped for Skills targets where persona is not surfaced |
| 3 | `## Tone` | No | Often inlined into Identity for Copilot Studio; separate when it's substantial |
| 4 | `## Capabilities` | Yes | "What You Can Do" / "What You Cannot Do" lists. Universal in the legacy agents |
| 5 | `## Knowledge Sources` | Yes when knowledge bindings declared | References declared knowledge IDs from frontmatter |
| 6 | `## Tools` | Yes when tool bindings declared | References declared tool IDs from frontmatter |
| 7 | `## Workflow` | Yes | Step-by-step procedure for the primary task |
| 8 | `## Output Format` | No | Required when output structure matters (e.g. Casey's case-study format) |
| 9 | `## Response Templates` | No | Verbatim response strings as guardrails; common in legacy agents |
| 10 | `## Edge Cases` | Yes | What to do when the happy path fails. Includes "no results" handling |
| 11 | `## Examples` | Yes | At least one complete worked example. Critical for description / triggering |
| 12 | `## Validation Checklist` | No | Pre-deployment checks the author runs. Surfaces in `skl validate` warnings |
| 13 | `## References` | No | Pointer block to `references/` files for progressive disclosure |

Differences from the existing `docs/spec/compilation.md` ten-section canon:
- Adds **Response Templates** (universal in the legacy agents; not in the existing canon).
- Demotes **Tone** to optional (often inlined; rarely worth its own section).
- Renames implicit "Edge Cases" / "Error Handling" to **Edge Cases** explicitly.
- Drops **Knowledge Sources** / **Tools** to "required only when bindings are declared" rather than always-required (e.g. a simple skill with no external knowledge does not need a Knowledge Sources section).
- The existing canon's section order maps cleanly to the proposed order; this is a refinement, not a rewrite.

---

## 8. Per-platform compilation strategy

### 8.1 Anthropic Skills-native targets

For `claude-code`, `claude-cowork`, `ms-cowork`, and any future Skills-consuming surface (Microsoft Foundry, Claude API uploads, claude.ai uploads):

- Compile is a **filesystem operation**: copy the skill folder (SKILL.md + scripts/ + references/ + assets/) to `platforms/<id>/`.
- Strip the `skl:` frontmatter block before writing - or, more conservatively, leave it intact since Anthropic ignores unknown keys. Open question: see Q-007.
- Persona-stripping is irrelevant for these targets; Claude is the persona.
- Drop the `skl validate`-required Identity body section in the compiled artefact (or leave it; harmless either way).
- For surfaces that need a zip (claude.ai uploads), `skl compile` produces a `<name>.zip` under `platforms/claude-ai/`. For MS Copilot Cowork, the compiled artefact is the folder placed in OneDrive; `skl deploy` does the OneDrive write.

Net: ~90% of the value of authoring a master skill comes free.

### 8.2 VS Code

VS Code is the most flexible consumer. Each skill in a repo can produce **one or both** of:

- **Agent Skill variant** at `platforms/vscode/skill/SKILL.md` - identical to the Anthropic-native artefacts. Loaded from `.github/skills/` or `.claude/skills/` in the consuming repo.
- **Custom Agent variant** at `platforms/vscode/agent/<name>.agent.md` - if the master frontmatter declares a `vscode:` block (per §7.3). Includes persona / tools / model / handoffs in the `.agent.md` frontmatter; body is the markdown skill content. Loaded from `.github/agents/`.

Decision point per skill: ship as Skill (Anthropic-portable, on-demand) or as Custom Agent (persistent persona, tool-restrictive, handoff-capable) or both. The frontmatter declaring (or omitting) a `vscode:` block is the signal.

Default: ship as Skill only, unless the author opts in to the Custom Agent variant. Open question: see Q-008.

### 8.3 Copilot Studio

The hard target. Single 8,000-char free-text instructions field.

Compile order:
1. Resolve variables in template form (tokens remain `{{variables.x}}`, substituted at deploy per D-007).
2. Build the instructions text in canonical order: Identity + Tone (inlined) - Capabilities - Knowledge Sources (with `/`-references to UI-bound source names) - Tools (`/`-references) - Workflow - Output Format - Response Templates - Edge Cases - Examples.
3. Strip Anthropic-Skills-specific sections that don't apply (References block).
4. Enforce per-skill budget: `skl.budgets.copilot-studio` or 8000 default. Fail the compile if exceeded.
5. Run the existing `skl lint` rules (no em/en-dashes, AU spellings, credential-shaped strings, etc.).

UI-bound knowledge sources and tools are declared in the master frontmatter as bindings (per §7.3). The compiler emits `/<binding-name>` references inline; the user is responsible for adding the corresponding SharePoint sources / connectors in Copilot Studio. `skl validate` warns when a binding references a name the local repo has no record of (no current Copilot Studio API to verify against, but the binding name is a hint).

Persona surfaces by default for Copilot Studio (per the existing D-006 in the parent project). Identity section is required.

### 8.4 M365 declarative agents

Compile produces two files:
- `platforms/m365/declarative-agent.json` - the v1.7 manifest with `version`, `name`, `description`, `instructions`, `capabilities[]`, `conversation_starters[]`, `behavior_overrides`, `disclaimer`, optionally `actions[]` and `editorial_answers`.
- `platforms/m365/instructions.md` - the human-readable version of the instructions string (the manifest needs the string inline; the markdown is for diff / review).

Mapping from master to manifest:
- `name` (master) -> `name` (manifest); truncate / warn if &gt; 100 chars.
- `description` (master) -> `description` (manifest); enforce &le; 1,000.
- Body compiled to `instructions` string &le; 8,000 chars; same compile order as Copilot Studio, persona **stripped** by default (per existing D-006).
- `skl.knowledge[].bindings.m365` -> `capabilities[]` entries (typed: `OneDriveAndSharePoint`, `GraphConnectors`, etc.).
- `skl.conversation_starters` -> `conversation_starters[]`, truncated to 12.
- `skl.m365.behavior_overrides` -> manifest `behavior_overrides`.
- `skl.m365.disclaimer` -> manifest `disclaimer.text` &le; 500.
- `skl.tools[].bindings.m365` -> `actions[]` plugin refs.

`skl validate` enforces v1.7 schema match against a bundled local copy of the schema.

### 8.5 Sub-agent / handoff modelling

This is genuinely cross-cutting. M365 has `worker_agents[]` (preview), VS Code has `agents[]` + `handoffs[]`, Claude Code subagents are a sibling feature, Claude Cowork bundles sub-agents. The master shape should model handoffs declaratively in the `skl:` block (e.g. `skl.handoffs[]`) and let each compiler project. This affects multi-agent system (MAS) composition, which D-009 already declares is a cross-repo concern. Recommendation: **defer handoff modelling to a follow-up analysis** (v0.2+); for v0.1 the master shape carries handoffs only as a placeholder. See Q-011.

---

## 9. Risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Anthropic Skills format changes substantially (breaks our base) | Medium | High | Pin the base-layer field set in a decision record; track Anthropic's spec page; major-bump `skl` if Anthropic introduces a breaking change |
| Anthropic introduces a frontmatter field that collides with our `skl:` namespace | Low | Medium | `skl:` is unlikely to collide (vendor-prefixed), but `skl-knowledge`, `skl-tools` etc. are at risk. Stick to a single top-level `skl:` object |
| M365 declarative-agent schema iterates faster than we can track (currently v1.3 -> v1.7 inside 6 months) | High | Medium | Bundle the schema JSON in `_shared/schemas/`; pin per-skill via `skl.m365.schema_version`; `skl validate` warns on stale schema |
| VS Code's `.chatmode.md` -> `.agent.md` migration completes and the legacy format is removed | Medium | Low | Ship `.agent.md` from the outset; do not emit `.chatmode.md` |
| Copilot Cowork's "accepts SKILL.md" claim turns out to mean a constrained subset | Medium | Medium | Run a first-class integration test once Frontier access is available; flag mismatches before users hit them |
| Persona stripping for Skills targets removes content the author wanted preserved | Low | Low | Make stripping opt-out via `skl.persona.strip_for: [...]`; default conservative |
| Variables declared in master frontmatter leak into Anthropic-native targets unprocessed | Medium | Medium | Compiler strips `{{variables.x}}` and `{{knowledge.id}}` tokens for Skills-native artefacts during deploy (per D-007), substituting at the same point regardless of target |
| Authors write a 4,000-char skill that compiles fine to Skills targets but breaks Copilot Studio compile when they enable that platform later | High | Medium | `skl budget` warns even when target not enabled; spec authors should size for the tightest enabled target |
| The 10-section canonical body becomes a checkbox exercise rather than load-bearing structure | Medium | Medium | Mirror Anthropic's "theory of mind" guidance in `skl lint`; warn on empty sections, not on missing sections |
| Microsoft Cowork OneDrive 50-skill cap becomes binding | Low | Low | `skl deploy` warns when approaching cap; the cap is per-user, not per-org |
| Claude Code subagent format and Custom Skills format both live under `.claude/`, confusing users about which is which | Medium | Low | `skl init` repo-scoped form makes the choice explicit; docs disambiguate |

---

## 10. Bibliography (dated)

All sources fetched between 17 and 18 May 2026.

**Anthropic / Claude:**
- [Anthropic Agent Skills overview](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/overview) - canonical SKILL.md spec, frontmatter constraints, progressive disclosure model, cross-surface availability matrix.
- [anthropics/skills](https://github.com/anthropics/skills) - public Agent Skills repository (README); folder structure conventions.
- [anthropics/skills - skill-creator SKILL.md](https://github.com/anthropics/skills/blob/main/skills/skill-creator/SKILL.md) - the canonical authored example, including a literal `## Cowork-Specific Instructions` section.
- [Claude Code subagents](https://code.claude.com/docs/en/sub-agents) - subagent file format, frontmatter, tool inheritance, invocation model.
- [Anthropic engineering: Equipping agents for the real world with Agent Skills](https://www.anthropic.com/engineering/equipping-agents-for-the-real-world-with-agent-skills) - architecture, real-world applications.
- [Claude Cowork product page](https://www.anthropic.com/product/claude-cowork) - desktop agent overview.
- [Cowork: Claude Code power for knowledge work](https://claude.com/product/cowork) - bundles skills + connectors + sub-agents.

**Microsoft Learn (with `updated_at` dates):**
- [Copilot Studio: authoring instructions](https://learn.microsoft.com/en-us/microsoft-copilot-studio/authoring-instructions) - updated 10 Apr 2026. Instructions field model, `/`-references, citation-format warning.
- [Copilot Studio: requirements and quotas](https://learn.microsoft.com/en-us/microsoft-copilot-studio/requirements-quotas) - updated 13 May 2026. 8,000-char instructions limit, 100 skills / 1,000 topics / 200 trigger phrases per agent.
- [M365 declarative-agent manifest v1.7](https://learn.microsoft.com/en-us/microsoft-365/copilot/extensibility/declarative-agent-manifest-1.7) - updated 14 May 2026. Authoritative manifest schema.
- [M365 declarative-agent manifest v1.3](https://learn.microsoft.com/en-us/microsoft-365/copilot/extensibility/declarative-agent-manifest-1.3) - updated 6 Mar 2026. Older but still live.
- [Microsoft Copilot Cowork overview (Frontier)](https://learn.microsoft.com/en-us/microsoft-365/copilot/cowork/) - updated 6 May 2026. OneDrive skill discovery, 50-skill cap, built on Anthropic tech.
- [Microsoft 365 blog: Copilot Cowork](https://www.microsoft.com/en-us/microsoft-365/blog/2026/03/09/copilot-cowork-a-new-way-of-getting-work-done/) - 9 Mar 2026 announcement.

**VS Code / GitHub Copilot:**
- [VS Code custom agents (formerly chat modes)](https://code.visualstudio.com/docs/copilot/customization/custom-agents) - `.agent.md` frontmatter schema, migration story.
- [VS Code Agent Skills](https://code.visualstudio.com/docs/copilot/customization/agent-skills) - VS Code natively consumes Anthropic SKILL.md.
- [VS Code custom chat modes (legacy)](https://code.visualstudio.com/docs/copilot/customization/custom-chat-modes) - the soon-to-be-replaced surface.
- [VS Code custom instructions](https://code.visualstudio.com/docs/copilot/customization/custom-instructions) - `*.instructions.md` complementary surface.

**Internal evidence (this repo + sibling):**
- `/home/dthomas/dev/prompt_library/copilot_studio/prompts/{casey,cappi,eddy,histy,qually,skilly}_agent_spec.md` - six hand-authored agent specs, mined by a sub-agent.
- `/home/dthomas/dev/prompt_library/copilot_studio/templates/copilot_template.md` - the Copilot template the user has been working from.
- `/home/dthomas/dev/prompt_library/claude_ai/templates/claude-{project-instructions,prompt}-template-2025.md` - Claude-side templates.
- `/home/dthomas/dev/prompt_library/copilot_studio/docs/microsoft-copilot-agents-guide.md` and `quick_reference_guide.md` - house-authored guidance on the Copilot Studio surface.
- `/home/dthomas/dev/skl/docs/spec/compilation.md` - the existing 10-section canon, due for refinement per §5.

---

## 11. See also

- [`../spec/compilation.md`](../spec/compilation.md) - the existing per-platform compiler spec, to be revised in light of §7-§8 above.
- [`../spec/manifest.md`](../spec/manifest.md) - the `skill-repo.yaml` schema; unaffected by this analysis.
- [`../decisions/D-007-three-tier-values.md`](../decisions/D-007-three-tier-values.md) - variables and substitution timing (informs §7.3 `skl.variables`).
- [`../decisions/D-008-secrets-separation.md`](../decisions/D-008-secrets-separation.md) - secrets are not master-skill-modelled; this analysis assumes the existing model.
- [`../decisions/D-011-shared-kit-fetched.md`](../decisions/D-011-shared-kit-fetched.md) - `_shared/schemas/skill.frontmatter.schema.json` is where the codified schema for §7.3 will land.
- [`../open-questions.md`](../open-questions.md) - **Q-005 through Q-012** are raised by this analysis.

---

*Authored 18 May 2026 to inform spec work on the SKILL.md authoring model. Re-verify Anthropic Skills and VS Code field-level claims before they land in `docs/spec/`; both formats are iterating.*
