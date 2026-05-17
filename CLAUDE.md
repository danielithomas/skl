# CLAUDE.md

Operator manual for any Claude session working in the `skl` repo. Read this before touching anything else.

---

## What this repo is

`skl` is the CLI toolkit that compiles, validates, lints, budgets and deploys portable AI-skill definitions across six platforms (Copilot Studio, M365 Copilot, MS Cowork, Claude Code, Claude Cowork, VS Code chat modes). Single binary on PATH after `pipx install skl`.

**This repo holds the toolkit, not the skills.** Skills themselves live in skill-host repos (e.g. `ai-skills-lib`, `ea-assessment`). If a request is about authoring a *skill*, it does not belong here.

**Status: pre-v0.1.** The CLI surface and manifest schema are specified in `docs/spec/`; the implementation has not started. `skl --version` works; everything else is a stub.

**Design history**: this repo was extracted from [`ai-skills-lib`](https://github.com/danielithomas/ai-skills-lib) per decision D-010. The originating decision log lives at `ai-skills-lib/analysis/06_decision_log.md`. Decisions that constrain `skl`'s behaviour are distilled in `docs/decisions/` here.

---

## Folder map

```
skl/
├── README.md                              ← landing page; leads with the skillctl distinction
├── CLAUDE.md                              ← this file
├── LICENSE                                ← MIT
├── CHANGELOG.md                           ← Keep a Changelog format
├── pyproject.toml                         ← uv-managed; declares `skl` console_script
├── uv.lock                                ← committed for reproducibility
├── .python-version                        ← uv convention
├── docs/
│   ├── spec/                              ← authoritative specification for `skl`
│   │   ├── README.md
│   │   ├── cli.md                         ← CLI surface
│   │   ├── manifest.md                    ← skill-repo.yaml schema
│   │   ├── infrastructure.md              ← install, discovery, versioning
│   │   ├── values-and-secrets.md          ← D-007 + D-008 distilled
│   │   └── compilation.md                 ← per-platform compilers + validators
│   └── decisions/                         ← decisions that constrain skl's behaviour
│       ├── README.md
│       ├── D-007-three-tier-values.md
│       ├── D-008-secrets-separation.md
│       ├── D-009-multi-repo-architecture.md
│       ├── D-010-toolkit-identity.md
│       └── D-011-shared-kit-fetched.md
├── src/
│   └── skl/
│       ├── __init__.py                    ← __version__
│       ├── __main__.py                    ← `python -m skl` entry point
│       └── cli.py                         ← Click / argparse top-level CLI
├── tests/
│   ├── __init__.py
│   └── test_cli.py                        ← smoke tests
└── .github/workflows/
    └── ci.yml                             ← ruff + pytest on push/PR
```

---

## Working conventions

- **Python 3.11+.** Type hints required on public functions. `from __future__ import annotations` at the top of every module.
- **Tooling**: `uv` for env / lock / build / publish. `ruff` for lint and format. `pytest` for tests. No `poetry`, no `black`, no `flake8`.
- **All YAML access goes through `skl.manifest`** (which uses `ruamel.yaml` in round-trip mode to preserve user-authored comments, ordering and formatting across rewrites). Do not import `ruamel.yaml` or `yaml` directly elsewhere in the codebase - extend `skl.manifest` with a new helper if you need a different access pattern.
- **Australian English** in user-facing strings, help text, errors, docs. `organise`, `realise`, `colour`, `catalogue`, `optimisation`. Currency AUD. Dates `DD MMM YYYY`.
- **No em-dashes (`—`) or en-dashes (`–`).** Use a hyphen with surrounding spaces (` - `) instead. `skl lint` will eventually enforce this on compiled skill output; manually enforce it in this repo's own docs and strings.
- **No "as an AI", "I cannot fulfill", "in order to"** in any user-facing output.
- **Semver** for the package. Major bumps reserved for breaking changes to `skill-repo.yaml`, compiler output contracts, or `_shared/` integration points (per D-010).
- **The CLI binary is `skl`.** Never `pl` (the legacy name from the prompt-library era - see D-010 rationale for why it was retired).
- **Distinction from `skillctl`** is load-bearing. Any user-facing docs (README, `--help`, error messages where relevant) should make the contrast clear when there is any risk of confusion.

---

## Specification source of truth

`docs/spec/` is authoritative for `skl`'s behaviour. Implementation must match the spec, not the other way around. If you find a divergence:

1. Decide whether the spec is wrong or the implementation is wrong.
2. Update one or the other in a discrete commit.
3. Do not silently drift.

If you propose a behaviour change that affects external contracts (CLI surface, manifest schema, compiler output shape), it warrants a decision document in `docs/decisions/` before code lands.

---

## Key decisions that constrain `skl`

Listed in `docs/decisions/`. The five-second summary:

| ID | What it constrains | Where it lives in `skl` |
|----|--------------------|--------------------------|
| **D-007** | Three-tier values model; substitution at deploy time, not compile time; committed `platforms/` artefacts are template-form | `skl deploy`, `skl values *` |
| **D-008** | Secrets separated from config; pluggable backend (`keyring` default, plus `azure_keyvault`/`onepassword`/`vault`/`file`); `file` is dev-only and CI fails closed on it | `skl secrets *`, `skl lint` (credential detection), `skl values check` (reject secret-like keys) |
| **D-009** | Multi-repo architecture; `skl` is one of four repo classes; each skill-host repo declares itself via `skill-repo.yaml` | `skl init`, repo discovery |
| **D-010** | Toolkit identity: extracted to this repo; binary named `skl`; `pl` is retired | All of `skl` |
| **D-011** | Shared kit fetched via `skl shared sync` from `ai-skills-shared`; pinned, committed local copy in each skill-host repo; `_shared/local/` overlays apply last | `skl shared sync`, `skl validate` (drift detection) |

If a task touches any of the above, read the decision file before designing.

---

## Out of scope for this repo

- **Authoring skills.** That happens in skill-host repos. `skl` only validates, compiles and deploys what those repos produce.
- **Distribution of compiled skills** (the `skillctl` job). `skl` may one day emit packages consumable by a distribution tool, but that is a v1.x+ concern. See `docs/decisions/` for the open question.
- **The shared kit itself** (style rules, personas, templates, schemas). That lives in `ai-skills-shared` (planned). `skl` consumes the kit; it does not own it.
- **Tenant / customer values**. Those live in a sibling private values repo per D-007. `skl values sync` reads them; the repo itself is not concerned with their content.
- **LLM-graded behavioural tests** for compiled skills. Deferred to v1.1 (per D-004 in the parent project).

---

## When in doubt

1. Read the relevant `docs/spec/<area>.md` file. It is the spec.
2. Check `docs/decisions/` to see whether the question is already settled.
3. Cross-reference the parent project's `ai-skills-lib/analysis/` for full historical context.
4. If still unclear, **ask the user** rather than picking a direction.

---

*Last updated: 17 May 2026. Keep this file short. Spec lives in `docs/`.*
