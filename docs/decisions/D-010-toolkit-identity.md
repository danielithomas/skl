# D-010 - Extract the toolkit to its own repo; rename CLI binary to `skl`

| Field | Value |
|-------|-------|
| **ID** | D-010 |
| **Date** | 17 May 2026 (decided in parent project) |
| **Status** | Final |
| **Owner** | Daniel Thomas |
| **Parent record** | [`ai-skills-lib/analysis/06_decision_log.md` §D-010](https://github.com/danielithomas/ai-skills-lib/blob/main/analysis/06_decision_log.md) |

## Question

Where should the toolkit code live in the multi-repo model (D-009), and what should the CLI binary be called?

## Decision

- **Location**: extract immediately to a dedicated tooling repo named `skl` (this repo).
- **Name**: rename the CLI binary from the legacy `pl` to **`skl`**.

Specifically:

1. The repo, the PyPI distribution, and the CLI binary all share the same name: `skl`. Install via `pipx install skl` (or `uv tool install skl`).
2. `skl` follows semver. Major bumps are reserved for breaking changes to `skill-repo.yaml`, compiler output contracts, or shared-kit integration points. Each skill-host repo pins a compatible range in `skill-repo.yaml` under `skl_version` (e.g. `">=1.0,<2.0"`).
3. `skl` walks up from cwd looking for `skill-repo.yaml`; the first match wins. Without one, only global commands run.
4. **No copy script is needed** for the extraction: the toolkit did not yet exist as code, so the extraction is "author the toolkit in the new `skl` repo from scratch, using D3 as the spec".
5. The legacy `pl migrate` verb is re-scoped: in-repo legacy migration only (e.g. moving Casey from `copilot_studio/` to `skills/` inside `ai-skills-lib`). It is no longer the entry point for bringing in external libraries; specialist libraries live in their own skill-host repos (per D-009).

## What this constrains in `skl`

The decision essentially defines this repo. Every other constraint follows:

- **Repo identity**: `github.com/danielithomas/skl`.
- **PyPI distribution**: `skl`.
- **Binary on PATH**: `skl`.
- **License**: MIT.
- **Language**: Python 3.11+.
- **Packaging**: `uv` (with `hatchling` build backend).
- **`pl` is retired** as a CLI name. Any reference to `pl` in code, docs, help text, or error messages is a defect.

## Rationale - location

Extracting immediately (rather than after Casey migration proves the format) exercises the multi-repo install path early and keeps `ai-skills-lib` free of toolkit gravity. Since no code existed yet, the extraction cost was purely "where do the new files land". Deferring would have coupled the toolkit's first release to `ai-skills-lib`'s release rhythm.

## Rationale - name

The CLI name decision was forced by collision analysis. Three candidates were ruled out:

- **`pl`** (the legacy name from the prompt-library era): taken on PyPI with an "UNKNOWN" summary; shadows the SWI-Prolog launcher (`/usr/bin/pl`) on Linux.
- **`skill`**: taken on PyPI by "AI Agent Skill Search and Management" (directly in our domain); collides with the procps `/usr/bin/skill` binary.
- **`sbuild`**: collides with the Debian package builder and under-scopes the toolkit (build is one verb among ten-plus).

`skl` is clean on PyPI, not on PATH on a representative Ubuntu machine, reads as "skill" without locking the tool to a specific ecosystem, and is the shortest viable option.

## Risk flag (closed)

`skillctl` (https://pypi.org/project/skillctl/) exists in adjacent territory: it is a *distribution* tool that discovers SKILL.md files across GitHub registries and installs them by symlink into agent skill directories. After review (P-008 in the parent project), the conclusion was that `skillctl` is clearly distinct from `skl` - it is `npm install` for skills, while `skl` is the compiler-and-deployer that produces what gets installed. The two SKILL.md formats are incompatible. Future-state integration (`skl deploy` emitting packages consumable by `skillctl install`) is tracked as P-009.

The repo README opens with the `skl` vs `skillctl` distinction so casual readers do not confuse the two.

## See also

- [`README.md`](../../README.md) - leads with the skillctl distinction.
- [`docs/spec/infrastructure.md`](../spec/infrastructure.md) - installation, repo discovery, versioning.
- [`docs/decisions/D-009-multi-repo-architecture.md`](./D-009-multi-repo-architecture.md) - the architectural context.
- Parent project decision log for the full rationale and risk-flag closure.
