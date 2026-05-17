# D-007 - Three-tier values model with sibling values repo

| Field | Value |
|-------|-------|
| **ID** | D-007 |
| **Date** | 12 May 2026 (decided in parent project) |
| **Status** | Final |
| **Owner** | Daniel Thomas |
| **Parent record** | [`ai-skills-lib/analysis/06_decision_log.md` §D-007](https://github.com/danielithomas/ai-skills-lib/blob/main/analysis/06_decision_log.md) |

## Question

Where should company-specific configuration (folder paths, SharePoint URLs, customer names, rate cards, etc.) live so that:

1. The skill-host repos stay portable across companies, and
2. Commercially-sensitive context does not enter the git history of any repo that might be shared more widely?

## Decision

A three-tier values model with a sibling private values repo at tier 2.

| Tier | Where it lives | Owns |
|------|----------------|------|
| **1 - Repo defaults** | `_shared/skill.config.yaml` and per-skill `style:` blocks in the skill-host repo | Cross-company defaults: AU English, AUD, no em-dashes, governance policies, `personas.surface_in` |
| **2 - Org / company values** | Sibling private repo (suggested name `<company>-skill-values`); synced into `./.values/` via `skl values sync` | Company-specific config: `consulting_company`, SharePoint URLs, rate card paths, branding, default consultant org |
| **3 - Engagement / customer overrides** | Passed at command time via `--values-file <path>` or `SKL_VALUES_OVERRIDE` env var; not committed to any repo | Per-engagement one-offs |

**Resolution order at substitution time: tier 3 > tier 2 > tier 1.** Higher tiers override lower. A required variable missing at every tier fails closed.

**Substitution happens at deploy time, not compile time.** Committed `platforms/` artefacts are template form; tokens (`{{variables.x}}`, `{{knowledge.id}}`, `{{tools.id}}`) remain unresolved. `skl deploy` performs final substitution using resolved tier 1 + 2 + 3 values at the moment of deploy. This amends D-001 (which mandates committing compiled artefacts) so that the commit promise is preserved without leaking sensitive values into git.

## What this constrains in `skl`

- **`skl deploy`** performs tier 1+2+3 substitution at deploy time. Sensitive values never appear in any committed file.
- **`skl values sync`** copies a chosen profile from a sibling private repo (path or git URL) into `./.values/active.values.yaml`. The destination is gitignored.
- **`skl values schema`** generates a JSON Schema from the union of all enabled skills' `variables[]`. The sibling values repo's CI runs `skl values check` against it.
- **`skl values check`** validates a values file: rejects secret-like keys (handled in D-008) and fails on missing required variables.
- **`skl compile`** writes template-form artefacts under `platforms/`. It does NOT substitute.
- **`skl lint`** flags unresolved `{{...}}` tokens that remain after deploy-time substitution as an error.

## Rationale

The pattern (code repo + config repo) is industry standard: Helm chart + values, Terraform module + tfvars, k8s manifest + ConfigMap. Adopting it makes skill-host repos intrinsically multi-tenant, keeps commercially sensitive context out of the git history of repos that may one day be shared, and gives a clean separation between "the IP / accelerator product" and "this customer's deployment context".

The three-tier model future-proofs against customer-site work without committing to that structure now: tier 3 overrides handle on-site engagements as a CLI flag, no repo structure needed.

## See also

- [`docs/spec/values-and-secrets.md`](../spec/values-and-secrets.md) - full operational detail.
- [`docs/decisions/D-008-secrets-separation.md`](./D-008-secrets-separation.md) - why secrets travel separately from these values.
