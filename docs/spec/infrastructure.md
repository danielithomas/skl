# Infrastructure: installation, discovery, versioning

How `skl` is installed, how it discovers a skill-host repo, and how versioning and compatibility work. Distilled from D7 §4 and §6.

---

## Installation

### Primary

```bash
pipx install skl
```

Creates an isolated environment and exposes `skl` on PATH. Recommended for end users.

### Alternative

```bash
uv tool install skl
```

Equivalent to `pipx install skl` using Astral's `uv`. Same outcome on PATH.

### Local development

```bash
git clone git@github.com:danielithomas/skl.git
cd skl
uv sync --all-extras --dev
uv run skl --version
```

`uv sync` reads `pyproject.toml` and `uv.lock`, creates a project venv, installs dependencies including the `dev` extras (`pytest`, `pytest-cov`, `ruff`). `uv run skl` invokes the entry point in that venv.

### Not supported

- **Git submodule.** The point of extracting `skl` from `ai-skills-lib` is to free it from consumer-repo gravity.
- **Vendored copy in a skill-host repo.** Always install through `pipx` or `uv tool install`. Skill-host repos pin the *version range* in `skill-repo.yaml`, not the code itself.

---

## Repo discovery

`skl` is repo-aware. Behaviour:

1. On invocation, `skl` walks up from `$PWD` looking for `skill-repo.yaml`. The first match wins.
2. If a manifest is found, the directory containing it is the **active skill-host repo**. Most commands operate on this repo by default.
3. If no manifest is found, `skl` runs only the **global subset** of commands (see [`cli.md`](./cli.md) §Global vs repo-scoped). Other commands exit with code 2 and the message `not inside a skill-host repo`.

A subtle case: if `skl init <new-repo>` is invoked from inside an existing skill-host repo, `skl` warns that nested skill-host repos are not supported and asks the user to confirm. There is no technical obstacle to nesting, but it is almost always a mistake.

---

## Versioning

### `skl` itself

Follows semver. Major bumps are reserved for breaking changes to any of:

- The `skill-repo.yaml` schema (see [`manifest.md`](./manifest.md)).
- The compiler output contract for any enabled platform (see [`compilation.md`](./compilation.md)).
- The `_shared/` integration points (the schemas in the shared kit `skl` consumes).

Minor bumps add new verbs, new platform targets, or new validation rules in a backward-compatible way. Patch bumps fix bugs and improve diagnostics.

### Skill-host repo compatibility

Each skill-host repo pins a compatible range under `skl_version` in `skill-repo.yaml`. `skl` checks this on every invocation and refuses to run if the installed version is outside the range, with an actionable message and exit code 4.

### `COMPATIBILITY.md`

This repo will publish a `COMPATIBILITY.md` recording, for each `skl` version, the range of `skill-repo.yaml` schema versions and `_shared/` kit versions it supports. The format is a small append-only table; users can verify support without running `skl`.

---

## The shared kit

`skl` does not own the shared kit (`_shared/skill.config.yaml`, personas, templates, schemas). The kit lives in `ai-skills-shared` (planned). `skl` *fetches* the kit via `skl shared sync` and writes a pinned, committed copy into each skill-host repo's `./_shared/`.

The detailed protocol is in [`cli.md`](./cli.md) under `skl shared sync` and [`docs/decisions/D-011-shared-kit-fetched.md`](../decisions/D-011-shared-kit-fetched.md).

Three things worth highlighting here:

1. **The shared kit is committed, not gitignored.** This is intentional: a fresh clone of a skill-host repo must be usable offline.
2. **`_shared/local/` overlays apply last.** Skill-host repos can override any piece of the kit without forking the kit itself.
3. **Drift detection** is part of `skl validate`. If `_shared/.kit_version` does not match `shared_kit.version` in the manifest, validation warns and lists divergent files.

---

## Auth and credentials

`skl` itself uses **no credentials** for its core compile / validate / lint / budget / test / index workflow. Those operate purely on files in the active repo.

Credentials are involved at two boundaries:

- **`skl shared sync`** - reads `shared_kit.source`. If that source is a private git remote, the user's git auth (SSH or HTTPS PAT) is required. `skl` does not handle git auth itself.
- **`skl deploy`** - resolves secrets via the configured backend (per D-008) and uses them to call platform APIs. The secrets backend is configured in `_shared/skill.config.yaml`.

`skl` never reads, writes, or transmits cloud credentials except through the configured secrets backend.

---

## Concurrency

`skl` commands are single-threaded by default. `skl compile --all` may parallelise per-skill compilation in a future release; for v0.1 it is sequential.

Long-running commands (`shared sync`, `deploy`) acquire an advisory lock on `.skl.lock` in the active repo to prevent concurrent invocations from corrupting the manifest or the `_shared/` copy.

---

## See also

- [`cli.md`](./cli.md) - command reference.
- [`manifest.md`](./manifest.md) - what `skill-repo.yaml` contains.
- [`docs/decisions/D-010-toolkit-identity.md`](../decisions/D-010-toolkit-identity.md) - why this repo exists.
- [`docs/decisions/D-011-shared-kit-fetched.md`](../decisions/D-011-shared-kit-fetched.md) - the shared-kit fetch model.
