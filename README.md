# skl

**`skl` (Skill) is a skill build and multi-platform deployment tool.**

One canonical `SKILL.md` source, six target platforms. `skl` validates, compiles, lints, budgets and deploys portable AI-skill definitions to Microsoft Copilot Studio, Microsoft 365 Copilot, Microsoft Cowork, Claude Code, Claude Cowork, and Visual Studio Code chat modes - from a single source-of-truth file.

---

## `skl` is not `skillctl`

The two names are close enough to be confused. They are not the same tool and do not overlap meaningfully.

| | `skl` | [`skillctl`](https://github.com/dvlshah/skillctl) |
|---|---|---|
| **Job** | Compiler and deployer | Distribution and install |
| **Analogy** | `make` / `cargo build` | `npm install` |
| **Output** | Platform-specific artefacts (six targets) | Symlinks to GitHub-hosted SKILL.md files in `~/.claude/skills/` etc. |
| **SKILL.md format** | Canonical body order: Identity, Tone, Capabilities, Knowledge, Tools, Workflow, Output, Edge Cases, Examples, Validation. Frontmatter-rich. | Different opinionated shape (When to Use, Core Principles, Common Mistakes, Examples) |
| **Values / secrets** | Three-tier values model, pluggable secrets backend | None |
| **Multi-agent skills** | First-class (orchestrator + sub-agents) | Not modelled |

If you want to install someone else's published SKILL.md onto your machine, you want `skillctl`. If you want to *produce* a SKILL.md that runs across multiple enterprise agent platforms with the right values, persona and character budget per platform, you want `skl`.

The two tools could one day integrate (`skl deploy` emitting packages consumable by `skillctl install`); see `docs/decisions/` for the open question.

---

## Status

**Pre-v0.1 - design complete, implementation has not started.** The CLI does nothing useful yet. This repository was extracted from the [`ai-skills-lib`](https://github.com/danielithomas/ai-skills-lib) project (per decision D-010 in that project's decision log), which is where the design history lives.

The current state:

- `docs/spec/` - authoritative specification for `skl` (CLI surface, manifest schema, infrastructure, values, compilation).
- `docs/decisions/` - the decisions that constrain `skl`'s behaviour, distilled from the parent project's decision log.
- `src/skl/` - Python package skeleton; `skl --version` works, everything else is `NotImplementedError`.
- `tests/` - smoke tests only.

---

## Install (planned)

```bash
pipx install skl                # primary - isolated install on PATH
uv tool install skl             # alternative
```

Neither will work yet because `skl` is not on PyPI. Local development:

```bash
git clone git@github.com:danielithomas/skl.git
cd skl
uv sync                         # installs in a project venv
uv run skl --version            # smoke test
```

---

## Quickstart (planned, not yet implemented)

```bash
skl init my-skills-repo         # scaffold a new skill-host repo (fetches shared kit internally)
cd my-skills-repo
skl init casey-case-studies     # scaffold a new skill inside the repo
skl validate                    # check frontmatter, body, knowledge contracts
skl compile                     # produce platforms/* artefacts
skl budget                      # character usage vs per-platform budget
skl test                        # run fixtures
skl deploy --skill casey-case-studies --platform claude-code
```

See `docs/spec/cli.md` for the full CLI surface.

---

## How `skl` fits with other repos

`skl` is one of four repo classes in the multi-repo skill architecture (D-009):

| Repo class | Examples | Role |
|------------|----------|------|
| **Tooling** (this repo) | `skl` | Holds the CLI |
| **Shared kit** | `ai-skills-shared` (planned) | Holds canonical `_shared/` content - style rules, personas, scaffold templates, schemas. Fetched into skill-host repos via `skl shared sync`. |
| **Skill-host** | `ai-skills-lib`, `ea-assessment`, future libs | Hold one or more skills. Declare themselves via `skill-repo.yaml`. |
| **Values** | `<company>-skill-values` (private) | Holds tier-2 company-specific values per D-007. |

See `docs/spec/infrastructure.md` and `docs/decisions/D-009-multi-repo-architecture.md`.

---

## Documentation

| Where | What |
|-------|------|
| `docs/spec/cli.md` | CLI surface: every verb, its arguments, its exit codes |
| `docs/spec/manifest.md` | `skill-repo.yaml` schema and validation rules |
| `docs/spec/infrastructure.md` | How `skl` discovers a skill-host repo, installation model, versioning |
| `docs/spec/values-and-secrets.md` | Three-tier values model and pluggable secrets backend |
| `docs/spec/compilation.md` | Per-platform compilers and validators |
| `docs/decisions/` | Decisions that constrain `skl`'s behaviour (D-007 through D-011) |

The full project design history lives in the parent project: [`ai-skills-lib/analysis/`](https://github.com/danielithomas/ai-skills-lib/tree/main/analysis).

---

## Licence

MIT. See `LICENSE`.

---

## Contributing

The project is pre-v0.1 and currently single-author. Issues and discussions welcome; PRs probably best held back until v0.1 ships and the contribution model is documented.
