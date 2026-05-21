# `skl` v0.1 implementation plan

The user-visible roadmap to v0.1. Each stage delivers something a user can do; prerequisite plumbing (schemas, parsing, IR) is folded into the earliest stage that needs it.

This document is the working roadmap, not a decision record. Revise it freely as stages land - prefer updating tasks in place over editing the past.

## Where we are

Already shipped:

- `skl init <name>` global form (scaffolds a new skill-host repo).
- `skl shared sync` (repo-scoped + global forms; fetches the shared kit per D-011).
- `skl validate` partial: manifest schema (Check 1), `skl_version` compatibility (Check 8), shared-kit drift (Check 6). Remaining check families are reported as `skipped` with a clear reason.
- Global `skl_version` compatibility guard at CLI entry with `SKL_IGNORE_COMPAT` escape hatch and fail-fast on parse failure.
- Decision records SKL-001 through SKL-010; parent-mirrored D-007 through D-011.

Open questions: empty. Every decision needed to reach v0.1 has landed.

## Sequencing

```
Stage 1 (authoring foundation) ──┬─→ Stage 2 (Skills-native compile) ──┐
                                 ├─→ Stage 3 (VS Code compile) ────────┤
                                 └─→ Stage 4 (Microsoft compile) ──────┤
                                                                       ├─→ Stage 5 (values + deploy)
                                                                       │       │
                                                                       │       ↓
                                                                       └→  Stage 6 (secrets)
                                                                              │
                                                                              ↓
                                                                       Stage 7 (test / migrate / deprecate)
```

Stages 2, 3, 4 can land in any order once Stage 1 is done; recommended order is 2 → 4 → 3 (Skills-native first because it exercises the compile pipeline at minimum complexity, Microsoft second because it surfaces the budget / persona / schema-version machinery, VS Code last because it composes the Skills-native variant with the Custom Agent variant).

Stages 5, 6, 7 depend on at least one compiler from Stage 2 existing - they can start before Stages 3 / 4 finish but can't ship without them.

---

## Stage 1: Authoring foundation

**User value:** "I can scaffold a SKILL.md in my repo and `skl validate` gives me actionable feedback on whether it's correctly authored."

### Acceptance criteria

- [ ] A user inside a skill-host repo can run `skl init <skill-name>` (or `skl add-skill <name>`) and get a scaffolded `skills/<skill-name>/SKILL.md` with the Anthropic-Skills base frontmatter + `skl:` block stubbed.
- [ ] `skl validate` runs all eight check families (or reports each one as `skipped` only when its scaffolding genuinely does not exist yet).
- [ ] `skl lint` enforces em-dash bans, AU spelling, unresolved-token detection, and credential-shaped-string detection on SKILL.md source.
- [ ] All schemas referenced by validate ship in the bundled fallback kit (per D-011 / SKL-004), with `skl shared sync` continuing to override from the user's kit source.

### Tasks

**Schemas (bundled fallback kit + format defined for the user kit):**

- [ ] `src/skl/schemas/skill.frontmatter.schema.json` - the master `skl:` block shape per SKL-004 (`schema_version`, `display_name`, `status`, `lifecycle`, `persona`, `enabled_platforms`, `variables[]`, `knowledge[]`, `tools[]`). No `handoffs` (per SKL-005). Required fields enforced.
- [ ] `src/skl/schemas/platforms/copilot-studio.schema.json` - sidecar input schema. `bindings` (knowledge + tools), `budget` (optional override).
- [ ] `src/skl/schemas/platforms/m365.schema.json` - sidecar input schema. `schema_version` **required** (per SKL-009), `bindings`, `behavior_overrides`, `conversation_starters`, `disclaimer`, `actions`, `editorial_answers`, `worker_agents`, `user_overrides`.
- [ ] `src/skl/schemas/platforms/vscode.schema.json` - sidecar input schema per SKL-007. Includes `emit_skill` (default `true`), `target`, `model`, `bindings`, `tools`, `agents`, `handoffs`, `hooks`, `mcp-servers`.
- [ ] `src/skl/schemas/platforms/m365/declarative-agent-manifest-1.7.json` - the Microsoft compiled-output schema, bundled as the v1.7 baseline per SKL-009.
- [ ] `src/skl/schemas/platforms/m365/index.json` - `{ default: "1.7", supported: ["1.7"], deprecated: [] }`.
- [ ] Decide: shared kit vs bundled fallback boundary. The bundled kit is what `skl` ships with for offline / fresh-install / test scenarios; the synced kit (when present) shadows it. Document the resolution order.

**Parsing:**

- [ ] `src/skl/skill_md.py` - new module. Reads SKILL.md → returns a `Skill` dataclass with frontmatter (`anthropic` and `skl` blocks separated), parsed body sections, and detected sidecar paths. Body sections split on canonical H2 anchors per analysis §7.4.
- [ ] `src/skl/sidecars.py` - new module. Reads `skl/platforms/<id>.yaml` files, validates against the corresponding schema, returns a `Sidecars` dataclass keyed by platform ID. Both modules go through `skl.manifest` for YAML (per CLAUDE.md).

**Validate completion:**

- [ ] `_check_frontmatter` (Check 2): SKILL.md frontmatter validates against `skill.frontmatter.schema.json`; the `anthropic` base fields (`name`, `description`) validate against their constraints (≤64 / ≤1000 chars).
- [ ] `_check_body` (Check 3): body has the required H2 sections per the platforms the skill targets (Identity required for surface targets per SKL-008; Capabilities + Workflow + Edge Cases + Examples always required per analysis §7.4).
- [ ] `_check_sidecars` (new): each `skl/platforms/<id>.yaml` validates against its schema; every binding ID cross-checks against `skl.knowledge[]` / `skl.tools[]`; sidecar presence vs `enabled_platforms` warning emitted (per SKL-004).
- [ ] `_check_knowledge_contracts` (Check 4): if `skl.knowledge[i].contract` references a file, the file exists and is parseable.
- [ ] `_check_cross_repo_dependencies` (Check 5): existing scaffold confirms manifest values; no new work.
- [ ] `_check_values_declarations` (Check 7): every `{{variables.X}}` token in the body / sidecars is declared in `skl.variables[]`.
- [ ] Update the deferred-checks list in `validate.py` to remove the ones that are now implemented.

**Init repo-scoped form:**

- [ ] `skl init <skill-name>` when run inside an existing skill-host repo scaffolds `skills/<skill-name>/SKILL.md` from the kit's scaffold template (or the bundled fallback).
- [ ] Optional `--platform <id>` flag scaffolds the matching `skl/platforms/<id>.yaml` sidecar with sensible defaults. For `m365`, the `schema_version` is read from the kit's `_shared/schemas/platforms/m365/index.json` `default` field per SKL-009.
- [ ] Refuse to create over an existing skill folder; suggest `--force` (out of scope for v0.1 - just refuse).

**Lint:**

- [ ] `src/skl/lint.py` - new module. Rule registry; each rule produces zero or more `LintFinding(severity, location, message)`. Initial rule set:
  - em-dash / en-dash detection (`—`, `–`)
  - US-spelling detection against a small list (`organize` / `realize` / `color` / `optimization` - the lint kit is in `_shared/lint/`)
  - credential-shaped strings (per D-008; regex set for AWS / Azure / GCP / OpenAI / Anthropic / generic `*_TOKEN=` patterns)
  - unresolved `{{variables.X}}` where X is not declared in `skl.variables[]`
  - banned phrases: "as an AI", "I cannot fulfill", "in order to"
- [ ] `skl lint` CLI verb wired in; supports `--all`, `--fix` (auto-fix where possible: em-dashes → ` - `; US → AU spellings).
- [ ] Exit codes: 0 if no findings, 1 if any error-severity findings, 0 if only warnings.

**Tests:**

- [ ] `tests/test_skill_md.py` - frontmatter parsing, body section splitting, sidecar discovery.
- [ ] `tests/test_validate.py` extensions - one test per new check family.
- [ ] `tests/test_init.py` extensions - repo-scoped form, platform-sidecar scaffolding, M365 schema-version pin.
- [ ] `tests/test_lint.py` - one test per rule; `--fix` produces expected output.
- [ ] End-to-end smoke: scaffold a skill, run `skl validate`, run `skl lint`, all pass on the scaffolded output.

**Docs:**

- [ ] Update `docs/spec/cli.md` `skl init`, `skl validate`, `skl lint` sections with the implemented behaviour.
- [ ] Update `docs/spec/manifest.md` if `skill-repo.yaml` gains fields (unlikely).
- [ ] Add `docs/spec/skill-md.md` (new) documenting the SKILL.md authoring contract: frontmatter shape, required body sections, sidecar layout, scaffolding command. Cross-reference SKL-004 / SKL-005 / SKL-008.
- [ ] `CHANGELOG.md` Unreleased entry covering the additions.

### Out of scope for this stage

- Any compilation (Stages 2 / 3 / 4).
- Values resolution beyond declaration validation (Stage 5).
- Per-skill persona override (`skl.persona.surface_for`) - deferred to v0.2 per SKL-008.

---

## Stage 2: Skills-native compile

**User value:** "I can `skl compile claude-code <skill>` (or `claude-cowork` / `ms-cowork`) and get a working Anthropic Agent Skill in `platforms/<id>/<skill>/`."

### Acceptance criteria

- [ ] `skl compile claude-code <skill-name>` produces `platforms/claude-code/<skill>/SKILL.md` (+ any `references/` / `scripts/` / `assets/` from source) with the `skl:` frontmatter block stripped per SKL-006.
- [ ] Same compiler reused for `claude-cowork` and `ms-cowork`; output paths differ but bytes are identical.
- [ ] Compiled SKILL.md leads with a `# Compiled by skl <version> from <source-path> on <YYYY-MM-DD>` provenance comment per SKL-006.
- [ ] `## Identity` body section stripped per SKL-008.
- [ ] `skl compile --all` compiles every skill in the repo for every platform in `enabled_platforms`.
- [ ] `skl index` regenerates `skills/SKILLS_INDEX.md` from the current skill set.

### Tasks

- [ ] `src/skl/compile/__init__.py` - new package. Public surface: `compile_skill(skill_root, platform_id) -> CompileResult`.
- [ ] `src/skl/compile/ir.py` - intermediate representation. `ResolvedSkill` dataclass: parsed SKILL.md + merged sidecar(s) + resolved knowledge contracts. Built once per skill, consumed by per-platform compilers.
- [ ] `src/skl/compile/skills_native.py` - one implementation for `claude-code`, `claude-cowork`, `ms-cowork`. Strips `skl:`, strips `## Identity` (per SKL-008), emits provenance line, copies sibling folders.
- [ ] `src/skl/compile/provenance.py` - shared helper for the top-line comment used by every compiler (SKL-006).
- [ ] `skl compile <platform>` CLI verb wired in. Supports per-skill (`--skill <name>`) and repo-wide (`--all`). Default `skl compile` with no args runs all enabled platforms for all skills.
- [ ] `src/skl/index.py` + `skl index` verb: scans `skills/*/SKILL.md`, builds `skills/SKILLS_INDEX.md` table with skill name, description, enabled platforms, status / lifecycle.

**Tests:**

- [ ] `tests/test_compile_skills_native.py` - byte-identical output for the three targets; provenance line present; `skl:` block absent; `## Identity` absent.
- [ ] `tests/test_compile_pipeline.py` - IR construction, sidecar merge, error paths (missing skill, unknown platform).
- [ ] `tests/test_index.py` - SKILLS_INDEX.md regenerates deterministically.

**Docs:**

- [ ] Revise `docs/spec/compilation.md` per-platform sections for the three Skills-native targets to match the implementation.
- [ ] Add a "How `skl compile` works" section (input/output contract, IR, deterministic output, provenance line).
- [ ] `CHANGELOG.md` Unreleased entry.

### Out of scope for this stage

- VS Code (Stage 3); Copilot Studio / M365 (Stage 4).
- Variable substitution. Compiled output is template-form per D-007; tokens remain. Substitution happens at deploy (Stage 5).

---

## Stage 3: VS Code compile

**User value:** "I can `skl compile vscode <skill>` and get both an Agent Skill variant and a Custom Agent variant ready for VS Code."

### Acceptance criteria

- [ ] `skl compile vscode <skill>` with no `skl/platforms/vscode.yaml` sidecar emits only the Skill variant at `platforms/vscode/skill/<skill>/SKILL.md`. Same byte-stream as `claude-code` for that skill.
- [ ] With a `vscode.yaml` sidecar present, both variants are emitted by default: Skill variant + Custom Agent variant at `platforms/vscode/agent/<skill>.agent.md`.
- [ ] `emit_skill: false` in the sidecar suppresses the Skill variant.
- [ ] Custom Agent frontmatter is composed from master SKILL.md + sidecar per SKL-007's mapping table.
- [ ] `.chatmode.md` never emitted under any setting.
- [ ] Custom Agent body retains `## Identity` (persona surfaces per SKL-008 for the Custom Agent variant).

### Tasks

- [ ] `src/skl/compile/vscode.py` - the two-stage VS Code compiler. Reuses Skills-native compiler for the Skill variant.
- [ ] Custom Agent frontmatter composition: lift `target`, `model`, `tools`, `agents`, `handoffs`, `hooks`, `mcp-servers` from sidecar; `description` + `name` from master SKILL.md.
- [ ] `tools:` array sourced from `bindings.tools` values per SKL-007.

**Tests:**

- [ ] `tests/test_compile_vscode.py` - sidecar absent: Skill only; sidecar present: both variants; `emit_skill: false`: Custom Agent only; persona retained in Custom Agent body; persona stripped from Skill variant body.

**Docs:**

- [ ] Update `docs/spec/compilation.md` `vscode` section to match (SKL-007 / SKL-008 already partially documented this; tighten with the implementation behaviour).
- [ ] `CHANGELOG.md` Unreleased entry.

---

## Stage 4: Microsoft compile

**User value:** "I can `skl compile copilot-studio <skill>` and `skl compile m365 <skill>` and get usable artefacts inside the 8K budget."

### Acceptance criteria

- [ ] `skl compile copilot-studio <skill>` produces `platforms/copilot-studio/instructions.md` in T-C-R order with `## Identity` surfaced per SKL-008.
- [ ] `skl compile m365 <skill>` produces `platforms/m365/declarative-agent.json` (with `version` matching the sidecar's `schema_version` per SKL-009) plus `platforms/m365/instructions.md`.
- [ ] 8K budget enforced at compile time for both; compile fails (exit 1) if exceeded.
- [ ] M365 compiled output validates against the bundled `_shared/schemas/platforms/m365/declarative-agent-manifest-<version>.json`.
- [ ] `skl budget` reports per-skill character usage versus the 8K cap.

### Tasks

- [ ] `src/skl/compile/copilot_studio.py` - T-C-R compiler. Inlines Identity + Tone, then Capabilities, Knowledge Sources (with `/<binding>` refs), Tools (`/<binding>` refs), Workflow, Output Format, Edge Cases, Examples.
- [ ] `src/skl/compile/m365.py` - JSON manifest + instructions emission. Reads sidecar's `schema_version`; emits `version: "<pinned>"` in the manifest; loads the matching bundled schema for output validation.
- [ ] `src/skl/budget.py` + `skl budget` verb: per-platform budget table; report character counts vs caps; expose `--all` for repo-wide check.
- [ ] Compile-time budget enforcement helper used by both compilers.
- [ ] Schema-version resolution: walk `_shared/schemas/platforms/m365/index.json`; error on missing, soft-warn on older-than-default, strong-warn on `deprecated` per SKL-009.

**Tests:**

- [ ] `tests/test_compile_copilot_studio.py` - T-C-R section order; Identity surfaced; 8K budget enforced; binding refs rendered as `/<name>`.
- [ ] `tests/test_compile_m365.py` - manifest validates against bundled schema; `version` field matches sidecar pin; missing-pin error; older-than-default warning; deprecated-version warning.
- [ ] `tests/test_budget.py` - budget calculations across all platforms.

**Docs:**

- [ ] Tighten `docs/spec/compilation.md` `copilot-studio` and `m365` sections.
- [ ] `CHANGELOG.md` Unreleased entry.

### Out of scope for this stage

- M365 schema versions beyond v1.7. Adding v1.8 / older versions to the bundled kit is a kit release, not an `skl` release per SKL-009.

---

## Stage 5: Values + deploy

**User value:** "I can `skl deploy --skill <name> --platform <id>` and the compiled artefact lands at the install location with template variables resolved."

### Acceptance criteria

- [ ] `skl values check` validates that every required variable across all skills is supplied by the active values profile; rejects secret-like keys per D-008.
- [ ] `skl values sync --from <path|url>` pulls a profile from the sibling private values repo (per D-007) into `./.values/`.
- [ ] `skl values schema` emits a JSON Schema for the union of all `skl.variables[]` declarations across the repo.
- [ ] `skl deploy --skill <name> --platform <id>` substitutes template tokens using the resolved values + secrets, then writes the substituted artefact to the platform's install location (or `--to <path>` for a dry-run target).
- [ ] Compiled artefacts under `platforms/` remain template-form (per D-001 + D-007); deploy reads them but does not rewrite them.

### Tasks

- [ ] `src/skl/values.py` - three-tier resolution (repo defaults → values profile → command-line overrides per D-007). Returns a flat `dict[str, str]` for the substitution step.
- [ ] `src/skl/deploy.py` + `skl deploy` verb: load compiled artefact, resolve values, substitute tokens, write to install location. Per-platform install paths configured under `skill-repo.yaml` `deploy.<platform>` (new manifest field; spec'd in this stage).
- [ ] `skl values check` / `skl values sync` / `skl values schema` verbs wired in.
- [ ] Reject secret-like keys (`*_secret`, `*_token`, `*_password` etc.) inside any tier-1 / tier-2 value source per D-008.
- [ ] Manifest schema updated for the `deploy.<platform>` block.

**Tests:**

- [ ] `tests/test_values.py` - three-tier resolution; missing-required errors; secret-key rejection.
- [ ] `tests/test_deploy.py` - per-platform deploy paths; token substitution; `--to` dry-run; deploy is idempotent (re-running produces the same output).

**Docs:**

- [ ] Update `docs/spec/values-and-secrets.md` to match the implementation.
- [ ] Update `docs/spec/cli.md` for the new verbs.
- [ ] Update `docs/spec/manifest.md` for the `deploy.<platform>` fields.
- [ ] `CHANGELOG.md` Unreleased entry.

### Out of scope for this stage

- Secrets backends (Stage 6). Deploy without secrets means template tokens for secret-typed variables remain unsubstituted - this stage's deploy fails (clear error) if any unresolved secret-typed token would land in the deployed artefact.

---

## Stage 6: Secrets

**User value:** "I can `skl secrets set <key>` and `skl deploy` resolves it via the configured backend at deploy time."

### Acceptance criteria

- [ ] `skl secrets backend` is configurable in `skill-repo.yaml` per D-008: `keyring` (default), `azure_keyvault`, `onepassword`, `vault`, `file`.
- [ ] `skl secrets get / set / list` operate via the configured backend.
- [ ] `skl deploy` resolves secret-typed variables through the backend at substitution time.
- [ ] `skl validate` / CI fail closed when the configured backend is `file` and the environment is detected as CI (per D-008).

### Tasks

- [ ] `src/skl/secrets/__init__.py` - backend abstraction. `SecretsBackend` protocol with `get(key) -> str | None`, `set(key, value) -> None`, `list() -> list[str]`.
- [ ] `src/skl/secrets/backends/keyring.py` - default backend, wraps `python-keyring`.
- [ ] `src/skl/secrets/backends/file.py` - dev-only backend reading from `./.secrets.yaml` (gitignored). CI detection (`CI=true` or known CI env vars present) refuses to read.
- [ ] `src/skl/secrets/backends/azure_keyvault.py` / `onepassword.py` / `vault.py` - thin wrappers around their respective SDKs. Initial implementation can be a stub raising `NotImplementedError` if the user opts into them in v0.1; mark as "preview" in docs.
- [ ] `skl secrets get / set / list` CLI verbs wired in.
- [ ] Manifest schema gains the `secrets.backend` field.

**Tests:**

- [ ] `tests/test_secrets_keyring.py` - via a mocked keyring.
- [ ] `tests/test_secrets_file.py` - reads from `.secrets.yaml`; CI detection blocks reads.
- [ ] `tests/test_deploy_secrets.py` - deploy resolves secret-typed variables via the configured backend.

**Docs:**

- [ ] Tighten `docs/spec/values-and-secrets.md` secrets sections.
- [ ] `CHANGELOG.md` Unreleased entry.

### Out of scope for this stage

- Azure Key Vault / 1Password / Vault as fully tested production backends. Initial implementations can be preview / best-effort with clear "report bugs" notes; v0.2 hardens them.

---

## Stage 7: Test, migrate, deprecate

**User value:** "I can `skl test` against fixtures, `skl migrate` an old agent file into a SKILL.md scaffold, and `skl deprecate` a skill cleanly."

### Acceptance criteria

- [ ] `skl test --skill <name>` runs `tests/test-cases.yaml` fixtures against the compiled artefact; reports per-fixture pass / fail. Structural assertions only (per D-004); no LLM-graded behaviour tests in v0.1.
- [ ] `skl migrate <legacy-path>` reads a legacy agent file (in-repo only per spec) and scaffolds a SKILL.md draft with the body content seeded.
- [ ] `skl deprecate <skill> [--in-favour-of <name>]` sets `skl.status: deprecated` on the skill's SKILL.md and updates the SKILLS_INDEX accordingly.

### Tasks

- [ ] `src/skl/testing.py` (named to avoid shadowing the test package): fixture loader for `tests/test-cases.yaml`, runner that exercises the compiled artefact against each fixture.
- [ ] `src/skl/migrate.py`: parses legacy agent format (best-effort scaffolding; SKILL.md is then validated manually).
- [ ] `src/skl/deprecate.py`: updates frontmatter, regenerates index.
- [ ] CLI verbs `skl test`, `skl migrate`, `skl deprecate` wired in.

**Tests:**

- [ ] `tests/test_testing.py` (or rename).
- [ ] `tests/test_migrate.py`.
- [ ] `tests/test_deprecate.py`.

**Docs:**

- [ ] Update `docs/spec/cli.md` for the three verbs.
- [ ] `CHANGELOG.md` Unreleased entry.

### Out of scope for this stage

- LLM-graded behavioural tests (deferred to v1.1 per D-004).

---

## After Stage 7: v0.1 ship checklist

- [ ] All 13 CLI verbs implemented per `docs/spec/cli.md`.
- [ ] All eight `skl validate` check families implemented.
- [ ] All six platforms compile.
- [ ] Three-tier values resolution + secrets resolution land at deploy time.
- [ ] CHANGELOG.md `[Unreleased]` rolled into a v0.1.0 entry; `pyproject.toml` version bumped.
- [ ] `COMPATIBILITY.md` created with the v0.1.0 row per `docs/spec/infrastructure.md`.
- [ ] `pipx install skl` + `skl init` smoke test from a clean machine.
- [ ] First skill-host repo (`ai-skills-lib` or sibling) cuts a v0.1.0 pin and confirms end-to-end.

## v0.2 deferred

Out of scope for v0.1, named here so the trail is intact:

- Cross-platform `skl.handoffs[]` abstraction (deferred per SKL-005).
- Per-skill persona override `skl.persona.surface_for` / `strip_for` (deferred per SKL-008).
- Hardened Azure Key Vault / 1Password / Vault secrets backends (preview-only in v0.1 per Stage 6).
- Cross-repo MAS composition surface (D-009 names this as a separate concern).
- `skl deploy` packages consumable by `skillctl install` (P-009 in the parent project; revisited post-v0.1 ship).

## v1.1 deferred (per parent project D-004)

- LLM-graded behavioural tests in `skl test`.
