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

**Status: complete (commits `9f3cb5e`, `91d80db`, `bb73158`, `5056c19`, `c7fb3e8`).**

**User value:** "I can scaffold a SKILL.md in my repo and `skl validate` gives me actionable feedback on whether it's correctly authored."

### Acceptance criteria

- [x] A user inside a skill-host repo can run `skl init <skill-name>` and get a scaffolded `skills/<skill-name>/SKILL.md` with the Anthropic-Skills base frontmatter + `skl:` block stubbed.
- [x] `skl validate` runs all eight check families. Cross-repo-dependencies remains `skipped` with a clear reason (needs git access).
- [x] `skl lint` enforces em-dash bans, AU spelling, unresolved-token detection, credential-shaped-string detection, and banned-phrase detection on SKILL.md source.
- [x] All schemas referenced by validate ship in the bundled fallback kit under `src/skl/schemas/`; the synced kit can shadow when `ai-skills-shared` exists (per D-011 / SKL-004).

### Tasks

**Schemas (bundled fallback kit + format defined for the user kit):**

- [x] `src/skl/schemas/skill.frontmatter.schema.json` - master `skl:` block per SKL-004.
- [x] `src/skl/schemas/platforms/copilot-studio.schema.json` - sidecar input schema.
- [x] `src/skl/schemas/platforms/m365.schema.json` - sidecar input schema with `schema_version` required per SKL-009.
- [x] `src/skl/schemas/platforms/vscode.schema.json` - sidecar input schema per SKL-007.
- [x] `src/skl/schemas/platforms/m365/declarative-agent-manifest-1.7.json` - compiled-output schema baseline.
- [x] `src/skl/schemas/platforms/m365/index.json` - `{ default: "1.7", supported: ["1.7"], deprecated: [] }`.
- [x] Bundled fallback resolution documented (see [`docs/spec/skill-md.md`](spec/skill-md.md)): `src/skl/schemas/` ships as the fallback, synced kit at `_shared/schemas/` shadows when present.

**Parsing:**

- [x] `src/skl/skill_md.py` - `Skill` dataclass; body sections split on H2 anchors; H2 inside code fences ignored.
- [x] `src/skl/sidecars.py` - `Sidecars` keyed by platform ID from `skl/platforms/*.yaml`.
- [x] `skl.manifest` gains `loads(text)` + `to_plain(obj)` so all YAML reads still go through one module per CLAUDE.md.

**Validate completion:**

- [x] `_check_frontmatter` (Check 2).
- [x] `_check_body` (Check 3) - Identity conditionally required per SKL-008; Capabilities / Workflow / Edge Cases / Examples always required; warn on H1 / `display_name` mismatch.
- [x] `_check_sidecars` (new per SKL-004) - schema validation + binding ID cross-references + sidecar-coverage warning.
- [x] `_check_knowledge_contracts` (Check 4).
- [x] `_check_values_declarations` (Check 7).
- [x] Deferred list trimmed to only `cross-repo-dependencies` (needs git access for pinned-SHA verification).

**Init repo-scoped form:**

- [x] `skl init <skill-name>` inside an existing skill-host repo scaffolds the skill folder.
- [x] `--platform <id>` (repeatable) scaffolds matching sidecars for non-Skills-native targets. M365 `schema_version` read from kit `index.json`.
- [x] Refuses to overwrite an existing skill folder.
- [x] Bundled scaffold template at `src/skl/templates/standalone-skill.md` + sidecar stubs; `{{KEY}}`-marker substitution via `skl.templates.render`.

**Lint:**

- [x] `src/skl/lint.py` with five rule families per the plan.
- [x] `skl lint` CLI verb + `--fix` auto-applies em-dash and AU-spelling fixes via per-occurrence substring replacement.
- [x] Exit codes: 0 on no errors (warnings allowed); 1 on any error.

**Tests:**

- [x] `tests/test_skill_md.py` (12 cases).
- [x] `tests/test_sidecars.py` (7 cases).
- [x] `tests/test_schemas.py` (35 cases).
- [x] `tests/test_validate.py` extensions for all new check families (19 new cases).
- [x] `tests/test_init.py` extensions for the repo-scoped form (15 new cases) - including end-to-end smoke (scaffold + validate-passes).
- [x] `tests/test_lint.py` (27 cases).
- [x] Total Stage 1 test surface: 220 tests pass; ruff clean; format clean.

**Docs:**

- [x] Updated `docs/spec/cli.md` for `skl init` (repo-scoped form), `skl validate` (all check families documented), `skl lint` (full rule table + fix model).
- [x] `docs/spec/manifest.md` unchanged - no new fields.
- [x] Added `docs/spec/skill-md.md` documenting the SKILL.md authoring contract end-to-end.
- [x] Added `docs/spec/skill-md.md` link to `docs/spec/README.md`; bumped maturity to "v0.1 in progress".
- [x] `CHANGELOG.md` Unreleased entry covering Stage 1.

### Out of scope for this stage

- Any compilation (Stages 2 / 3 / 4).
- Values resolution beyond declaration validation (Stage 5).
- Per-skill persona override (`skl.persona.surface_for`) - deferred to v0.2 per SKL-008.

---

## Stage 2: Skills-native compile

**Status: complete (PR `feat/stage-2-skills-native-compile`).**

**User value:** "I can `skl compile claude-code <skill>` (or `claude-cowork` / `ms-cowork`) and get a working Anthropic Agent Skill in `platforms/<id>/<skill>/`."

### Acceptance criteria

- [x] `skl compile claude-code <skill-name>` produces `platforms/claude-code/<skill>/SKILL.md` (+ any `references/` / `scripts/` / `assets/` from source) with the `skl:` frontmatter block stripped per SKL-006.
- [x] Same compiler reused for `claude-cowork` and `ms-cowork`; output paths differ but bytes are identical (asserted by `test_skills_native_targets_byte_identical`).
- [x] Compiled SKILL.md leads with a `# Compiled by skl <version> from <source-path> on <YYYY-MM-DD>` provenance comment per SKL-006.
- [x] `## Identity` body section stripped per SKL-008.
- [x] `skl compile` default behaviour compiles every skill in the repo for every platform in `enabled_platforms`; `--skill` / `--platform` flags filter.
- [x] `skl index` regenerates `skills/SKILLS_INDEX.md` from the current skill set, deterministically.

### Tasks

- [x] `src/skl/compile/__init__.py` - dispatcher + public surface (`build_ir`, `compile_skill`, `CompilerNotImplementedError`).
- [x] `src/skl/compile/ir.py` - `ResolvedSkill` IR + `CompileResult` + `build_ir(skill_root, repo_root)`.
- [x] `src/skl/compile/skills_native.py` - one implementation for the three Skills-native targets. Text-surgery transformations (`_remove_top_level_yaml_block`, `_remove_h2_section`) preserve author formatting outside the bits being rewritten. Copies sibling `references/` / `scripts/` / `assets/`; excludes `skl/` and `tests/`.
- [x] `src/skl/compile/provenance.py` - SKL-006 top-line comment with `now` and `version` parameters for deterministic tests.
- [x] `skl compile` CLI verb wired in. `--skill` / `--platform` / `--all` per spec; unimplemented platforms (vscode / copilot-studio / m365) report as `skip` with the stage pointer; unknown platforms / skills are errors.
- [x] `src/skl/index.py` + `skl index` verb: deterministic markdown table; first-line / 120-char description summarisation; pipe escaping; empty-cell rendering.

**Tests:**

- [x] `tests/test_compile_skills_native.py` (25 cases) - happy path, byte-identical multi-target output, frontmatter / Identity strip, sibling-folder copy + exclusions, dispatcher routing, transformation-helper unit tests including code-fence edge case.
- [x] `tests/test_compile_cli.py` (10 cases) - flag filtering, error paths, end-to-end smoke (init + compile).
- [x] `tests/test_index.py` (14 cases) - structure, sort order, determinism, missing / empty skills dir, parse-error skipping, pipe escaping, long-description truncation, multi-line first-line-only, CLI integration.
- [x] Total Stage 2 test surface: 49 new tests; 267 in the full suite; ruff + format clean.

**Docs:**

- [x] `docs/spec/compilation.md` - replaced three separate Skills-native sections with one unified section noting they share an implementation; added "How `skl compile` works" overview describing the IR + public surface + determinism guarantees; documented the SKL-006 provenance comment placement and the Anthropic-loader compatibility flag.
- [x] `docs/spec/cli.md` - `skl compile` updated with stage status, exit codes, no-auto-validate clarification; `skl index` description fleshed out.
- [x] `CHANGELOG.md` Unreleased entry covering Stage 2.

### Out of scope for this stage

- VS Code (Stage 3); Copilot Studio / M365 (Stage 4) - dispatcher reports them as `skip`.
- Variable substitution. Compiled output is template-form per D-007; tokens remain. Substitution happens at deploy (Stage 5).
- Verifying SKL-006's "provenance above the fence" against Anthropic's actual loader. The implementation matches the decision; if real-world loader testing shows the leading comment breaks frontmatter parsing, SKL-006 will be amended to "first line inside the frontmatter as a YAML comment" - the implementation is set up for that one-line flip.

---

## Stage 3: VS Code compile

**Status: complete (PR `feat/stage-3-vscode-compile`).**

**User value:** "I can `skl compile vscode <skill>` and get both an Agent Skill variant and a Custom Agent variant ready for VS Code."

### Acceptance criteria

- [x] `skl compile vscode <skill>` with no `skl/platforms/vscode.yaml` sidecar emits only the Skill variant at `platforms/vscode/skill/<skill>/SKILL.md`. Same byte-stream as `claude-code` for that skill (asserted by `test_skill_variant_bytes_match_claude_code`).
- [x] With a `vscode.yaml` sidecar present, both variants are emitted by default: Skill variant + Custom Agent variant at `platforms/vscode/agent/<skill>.agent.md`.
- [x] `emit_skill: false` in the sidecar suppresses the Skill variant.
- [x] Custom Agent frontmatter is composed from master SKILL.md + sidecar per SKL-007's mapping table.
- [x] `.chatmode.md` never emitted under any setting.
- [x] Custom Agent body retains `## Identity` (persona surfaces per SKL-008 for the Custom Agent variant).

### Tasks

- [x] `src/skl/compile/vscode.py` - `compile_vscode(ir, *, now)` entry point plus `_build_custom_agent_md`, `_compose_custom_agent_frontmatter`, `_compose_tools_list` helpers.
- [x] Refactor `skl.compile.skills_native` to expose `emit_skills_native(ir, output_root, *, now)` so the VS Code Skill variant reuses the Skills-native transformations without re-routing through the dispatcher.
- [x] `skl.manifest.dumps(obj)` - fresh-emission YAML helper used to serialise the Custom Agent frontmatter.
- [x] Custom Agent frontmatter composition per SKL-007: `name` / `description` from master; sidecar passthroughs for `target` / `model` / `agents` / `handoffs` / `hooks` / `mcp-servers` / `argument-hint` / `user-invocable` / `disable-model-invocation`.
- [x] `tools:` array sourced from sidecar `bindings.tools` (sorted by skill tool ID) merged with explicit `tools:` (declaration order preserved), deduped on first occurrence.
- [x] Dispatcher routes `vscode` to `compile_vscode`; `CompilerNotImplementedError` set narrowed to `{copilot-studio, m365}`.

**Tests:**

- [x] `tests/test_compile_vscode.py` (20 cases) covering variant emission rules, byte-identical Skill variant vs claude-code, Identity retention/strip per variant, provenance placement, frontmatter passthroughs, `tools` composition (bindings-only / explicit-only / merge-with-dedup / empty), sibling-folder behaviour, dispatcher routing, CLI integration.
- [x] `tests/test_compile_skills_native.py` parametrize narrowed (vscode removed from not-yet-implemented).
- [x] Total: 286 tests pass; ruff + format clean.

**Docs:**

- [x] `docs/spec/compilation.md` `vscode` section rewritten with the emission table and the Custom Agent frontmatter composition table.
- [x] `docs/spec/cli.md` `skl compile` Stage status reflects Stage 3 complete.
- [x] `CHANGELOG.md` Unreleased entry.

---

## Stage 4: Microsoft compile

**Status: complete (PR `feat/stage-4-microsoft-compile`).** All six v0.1 platforms now compile.

**User value:** "I can `skl compile copilot-studio <skill>` and `skl compile m365 <skill>` and get usable artefacts inside the 8K budget."

### Acceptance criteria

- [x] `skl compile copilot-studio <skill>` produces `platforms/copilot-studio/instructions.md` with `## Identity` inlined as preamble (per SKL-008) and the canonical-section order documented in `compilation.md`.
- [x] `skl compile m365 <skill>` produces `platforms/m365/declarative-agent.json` (with `version: "v<schema_version>"` matching the sidecar pin per SKL-009) plus `platforms/m365/instructions.md`. The manifest is validated against the bundled output schema before write.
- [x] 8K budget enforced at compile time for both; over-budget compiles raise `BudgetExceededError` and exit 1.
- [x] `skl budget` reports per-skill character usage versus the 8K cap as a deterministic table.

### Tasks

- [x] Shared compile utilities extracted to `src/skl/compile/_transforms.py` (`FENCE_RE`, `split_frontmatter_and_body`, `remove_top_level_yaml_block`, `remove_h2_section`, `rewrite_binding_tokens`). All compilers now share the same primitives.
- [x] `src/skl/compile/budget.py` - `PLATFORM_BUDGETS`, `BudgetExceededError`, `enforce_budget()` helper used by both Microsoft compilers.
- [x] `src/skl/compile/copilot_studio.py` - canonical-section composition with Identity + Tone inlined as preamble; knowledge / tools tokens rewritten to `/<binding>` UI refs.
- [x] `src/skl/compile/m365.py` - JSON manifest + instructions emission. Reads sidecar's `schema_version`; emits `version: "v<pinned>"`; loads the matching bundled schema for output validation; validates manifest before write.
- [x] Schema-version resolution per SKL-009: error on missing, soft-warn on older-than-default, strong-warn on `deprecated`. Kit `_shared/schemas/platforms/m365/index.json` shadows the bundled copy.
- [x] `src/skl/budget.py` + `skl budget` verb. Walks every skill x every budget-capped platform, builds a deterministic table.

**Tests:**

- [x] `tests/test_compile_copilot_studio.py` (16 cases) - section order, Identity/Tone inlining, token rewrites, default + sidecar budget, dispatcher + CLI integration including budget-failure path.
- [x] `tests/test_compile_m365.py` (20 cases) - manifest validation, version pin → manifest field mapping, Identity strip, bindings → capabilities/actions, conversation_starters string → object transform, passthrough fields, schema-version resolution (missing sidecar, missing field, unknown, deprecated warning, kit-index override), schema validation, 8K budget, dispatcher + CLI.
- [x] `tests/test_budget.py` (16 cases) - empty repo, uncapped-platform skip, per-platform measurement, overage flagging, sidecar override, multi-skill multi-platform, unparseable-skill skip, render formatting, CLI happy / overage / no-capped paths.
- [x] Total Stage 4 test surface: 52 new tests; 336 in the full suite; ruff + format clean.

**Docs:**

- [x] `docs/spec/compilation.md` `copilot-studio` and `m365` sections rewritten to match the implementation (section order, token rewrites, passthrough fields, schema resolution table, validation behaviour).
- [x] `docs/spec/cli.md` `skl compile` Stage status (all six platforms done) + `skl budget` section fleshed out with example output and the per-platform budget table.
- [x] `CHANGELOG.md` Unreleased entries covering all three parts of Stage 4.

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
