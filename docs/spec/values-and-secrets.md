# Values and secrets

How `skl` resolves variables in skills and how it handles credentials. Implements D-007 (three-tier values) and D-008 (config / secrets separation). Distilled from the parent project's `analysis/02_portable_skill_specification.md` §7 and the relevant entries in `analysis/06_decision_log.md`.

---

## Why this is a separate document

Values and secrets are the most likely places to leak commercially sensitive material into a git history or a published artefact. The behaviour is non-obvious in two key ways: substitution happens at *deploy time* not compile time, and secrets travel through a different machinery than values. Putting it all in one place avoids confusion.

---

## Three tiers of values (D-007)

A *value* is any non-secret variable a skill needs: `consulting_company`, `case_study_library_path`, `default_consultant_org`, rate-card filenames, etc.

| Tier | What it covers | Where it lives | Committed? |
|------|----------------|----------------|------------|
| **1 - Repo defaults** | Cross-company defaults: AU English, AUD, governance policies, `personas.surface_in`. Anything that should be the same for everyone using this library | `_shared/skill.config.yaml` (the shared kit) and per-skill `style:` blocks | yes, in the skill-host repo |
| **2 - Org / company values** | The consulting firm's profile: `consulting_company`, SharePoint URLs, rate-card paths, default branding | Sibling private values repo (suggested name `<company>-skill-values`), synced into `./.values/` via `skl values sync` | yes in the values repo (which is private); `./.values/` is gitignored in the skill-host repo |
| **3 - Engagement / customer overrides** | Per-engagement one-offs: customer name, project number, on-site-specific bindings | Passed at command time via `--values-file <path>` or `SKL_VALUES_OVERRIDE` env var | no |

### Resolution order

At substitution time: **tier 3 > tier 2 > tier 1**.

Higher tiers override lower. A required variable with no value at any tier fails closed with a clear error.

### Substitution timing

**Deploy time, not compile time.** This is the critical detail.

- Committed `platforms/` artefacts (per D-001) are **template form**. Tokens like `{{variables.consulting_company}}` and `{{knowledge.case_study_library}}` remain unresolved in the files in git.
- `skl deploy` performs the final substitution using resolved tier-1 + tier-2 + tier-3 values, immediately before copying / uploading to the target platform.

This preserves D-001's promise (non-developer one-line deploys via committed artefacts) while keeping commercially-sensitive values out of the skill-host repo's git history.

### Sync mechanism

```bash
skl values sync --from ../business-aspect-skill-values
skl values sync --from git@github.com:business-aspect/skill-values.git --profile default
```

- Copies the chosen profile into `./.values/active.values.yaml`.
- Writes the JSON Schema for the active skill set into `./.values/values.schema.json`.
- Both are gitignored.
- The sibling values repo's CI runs `skl values check` against the schema to catch drift early.

---

## Secrets (D-008)

A *secret* is anything that grants access: OAuth tokens, API keys, signing keys, service principal secrets. Secrets are first-class and distinct from config.

### Definitions, sharp

| Class | Examples | Where it belongs |
|-------|----------|------------------|
| Config | SharePoint URLs, customer names, rate cards, file paths | Tier-2 values repo |
| Secrets | OAuth tokens, bearer tokens, API keys, signing keys, service-principal secrets | The configured secrets backend - never in any values file or skill body |

### Pluggable backend

Configured in `_shared/skill.config.yaml`:

```yaml
secrets:
  backend: keyring        # keyring | azure_keyvault | onepassword | vault | file
```

| Backend | Notes |
|---------|-------|
| `keyring` (default) | Python `keyring` library. Reads / writes OS keychain: macOS Keychain, Windows Credential Manager, GNOME Keyring / Secret Service on Linux |
| `azure_keyvault` | Azure Key Vault. Auth via DefaultAzureCredential |
| `onepassword` | 1Password CLI (`op`). Requires the user to be signed in |
| `vault` | HashiCorp Vault. Auth via configured method |
| `file` | **Dev only.** Reads from `~/.skl/credentials.yaml` (gitignored). Triggers a warning on every invocation. CI fails closed on this backend |

### CLI surface

```bash
skl secrets get <key>            # resolve via the configured backend
skl secrets set <key>            # prompts for value via stdin
skl secrets list                 # enumerate known keys (no values)
```

---

## Forbidden patterns

### In values files

`skl values check` rejects any key whose name matches a secret-like pattern:

- `*_token`
- `*_secret`
- `*_key`
- `*_password`
- `*_credential`

Genuine secrets live in the secrets backend, not in values files. The check is fail-closed: any match aborts the sync.

### In skill bodies and compiled output

`skl lint` flags credential-shaped strings in compiled artefacts using the following heuristics:

- High-entropy strings beyond a threshold.
- Recognised credential prefixes: `eyJ` (JWT), `xoxb-` (Slack bot tokens), `sk-` (OpenAI), `ghp_` (GitHub PAT), and others maintained in the shared kit.

A flagged compile fails with exit code 1. The lint runs again at deploy time after substitution, in case a tier-3 values file (intentionally or otherwise) introduced a credential string.

### In deployed artefacts

`skl deploy` reads secrets via the configured backend and passes them to the platform's API at the moment of deploy. Secrets never:

- Appear in any value file at any tier.
- Appear in any committed artefact under `platforms/`.
- Appear in `skl` logs (even at debug level - logging strips known secret patterns).

---

## Worked example

Casey (case-study skill) needs the SharePoint path of the firm's case-study library and the firm's name to surface in attribution. Neither is a secret. Both are tier-2 values for the firm.

The skill declares:

```yaml
# casey-case-studies/SKILL.md frontmatter (excerpt)
variables:
  - name: consulting_company
    description: The name of the firm running the skill
    required: true
  - name: case_study_library_path
    description: SharePoint path or filesystem path to the case-study library
    required: true
```

The firm's values repo provides:

```yaml
# business-aspect-skill-values/default.values.yaml
consulting_company: Business Aspect
case_study_library_path: /sites/practice/case-studies
```

The compile pass writes `platforms/copilot-studio/instructions.md` with `{{variables.consulting_company}}` and `{{variables.case_study_library_path}}` still as tokens.

At deploy, `skl deploy --skill casey-case-studies --platform copilot-studio`:

1. Reads `./.values/active.values.yaml` (synced earlier from the firm's values repo).
2. Substitutes both tokens.
3. Lints the substituted output (no credential-shaped strings present).
4. Reads the Copilot Studio service-principal secret via `skl secrets get` (the `keyring` backend by default).
5. Calls Copilot Studio's deploy API with the substituted artefact and the resolved secret.

Neither the firm name nor the SharePoint path enters `skl`'s git history. The service-principal secret never enters any file at any point.

---

## On-site customer engagements

When a consultant operates on-site at a customer using customer-specific bindings, the tier-3 override carries the load:

```bash
SKL_VALUES_OVERRIDE=./engagements/acme-2026.yaml \
  skl deploy --skill casey-case-studies --platform copilot-studio
```

The engagement file holds the customer-specific overrides (e.g. a different `case_study_library_path` pointing at Acme's tenant). Tier 3 wins over the firm's tier-2 defaults.

If the engagement requires customer-specific secrets (an Acme tenant service principal), they live in the configured secrets backend on the consultant's machine, scoped by key name (`acme_copilot_studio_sp_secret`).

---

## See also

- [`cli.md`](./cli.md) - `skl values *` and `skl secrets *` command reference.
- [`docs/decisions/D-007-three-tier-values.md`](../decisions/D-007-three-tier-values.md).
- [`docs/decisions/D-008-secrets-separation.md`](../decisions/D-008-secrets-separation.md).
- Parent project `ai-skills-lib/analysis/02_portable_skill_specification.md` §7 - the full canonical model.
