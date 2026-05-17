# D-008 - Config and secrets are separate; pluggable secrets backend

| Field | Value |
|-------|-------|
| **ID** | D-008 |
| **Date** | 12 May 2026 (decided in parent project) |
| **Status** | Final |
| **Owner** | Daniel Thomas |
| **Parent record** | [`ai-skills-lib/analysis/06_decision_log.md` §D-008](https://github.com/danielithomas/ai-skills-lib/blob/main/analysis/06_decision_log.md) |

## Question

Genuine secrets (OAuth tokens, API keys, signing keys, service-principal secrets) need different handling from non-secret config (SharePoint URLs, rate card paths). Should secrets live in the same tier-2 values repo as config (per D-007), or in a distinct mechanism?

## Decision

Secrets are first-class and distinct from config.

| Class | Examples | Lives in |
|-------|----------|----------|
| Config | SharePoint URLs, customer names, rate cards | Tier-2 values repo (per D-007) |
| Secrets | OAuth tokens, API keys, signing keys, service-principal secrets | The configured secrets backend - never any values file or skill body |

**Default backend: OS keychain** via Python `keyring`. macOS Keychain, Windows Credential Manager, GNOME Keyring / Secret Service on Linux.

**Pluggable backends** configured in `_shared/skill.config.yaml`:

```yaml
secrets:
  backend: keyring | azure_keyvault | onepassword | vault | file
```

The `file` backend reads from `~/.skl/credentials.yaml` (gitignored) and is **dev-only**: it triggers a warning on every `skl secrets` invocation and CI fails closed on it.

## What this constrains in `skl`

- **`skl secrets get <key>`** resolves a secret via the configured backend.
- **`skl secrets set <key>`** writes (where the backend supports it; prompts for the value via stdin).
- **`skl secrets list`** enumerates known keys, never values.
- **`skl values check`** rejects keys matching secret-like patterns: `*_token`, `*_secret`, `*_key`, `*_password`, `*_credential`.
- **`skl lint`** flags credential-shaped strings in compiled artefacts using heuristics: high-entropy strings, recognised credential prefixes (`eyJ...`, `xoxb-...`, `sk-...`, `ghp_...`).
- **`skl deploy`** reads secrets via the configured backend and passes them to platform APIs at deploy time. Secrets never enter committed `platforms/` artefacts.
- **`skl` logs** strip known credential patterns at all log levels, including debug.

## Rationale

Config (SharePoint URLs etc.) and secrets (OAuth tokens etc.) have different sensitivity profiles and require different storage. Putting them together in the values repo would mean a stolen values repo grants access - materially worse than just leaking config.

OS keychain is the right first-line: it integrates with the consultant's existing security posture, works offline, and requires no extra infrastructure. The pluggable backend lets a firm adopt Azure Key Vault or 1Password later without changing skills or the toolchain.

The yaml-file fallback is explicit and warned about so solo developer use is not blocked, but CI fails closed on it to prevent accidental promotion to production.

## Forbidden in `skl`'s own code

- Reading or writing any tenant credential anywhere except through the configured backend.
- Logging secret material at any level.
- Embedding secret values in `platforms/` artefacts (the substituted output is for an in-memory hand-off to a platform API, not for disk).

These are properties the implementation must preserve, enforced by review and (where possible) by tests.

## See also

- [`docs/spec/values-and-secrets.md`](../spec/values-and-secrets.md) - operational detail including the worked example.
- [`docs/decisions/D-007-three-tier-values.md`](./D-007-three-tier-values.md) - why config and secrets are separated.
