# Open questions

Live questions and decisions-in-flight for `skl`. Each entry stays here forever - the audit trail of "what we discussed and why we picked X" is more useful than a clean slate. When a question lands a decision, its heading gets struck through and a "Resolved by" link points at the [decision file](decisions/).

## Conventions

- IDs are `Q-NNN`, local to this repo, numbered in order they were raised.
- Resolved questions are kept under "Resolved", in numeric order, with strikethrough on the heading and a link to the deciding [SKL-NNN](decisions/) record.
- A decision can resolve several questions; an open question can spawn several decisions and stay open until all are settled.
- Cross-link liberally between this file, decision files, and the PR or conversation that raised the question.

---

## Open

### Q-004 - Global `skl_version` compatibility guard: edge cases

The guard added in [SKL-003](decisions/SKL-003-global-compatibility-guard.md) fires on every invocation inside a skill-host repo, except `skl init` and `skl validate` which have their own handling. Several edge cases need a follow-up call before they bite:

- **Escape hatch.** Should there be an `SKL_IGNORE_COMPAT=1` env var or `--ignore-compat` flag for emergency cases - e.g. a user needs to run one urgent fix but the manifest's pinned range excludes the installed `skl`? If yes, scope - per-command, global, or only on certain commands?
- **Unparseable manifest.** Currently the guard silently skips when the manifest fails to parse, letting `skl validate` surface the parse error. Right call, or should the guard fail fast with a more descriptive "can't even parse your manifest, run `skl validate`" message?
- **`skl --version`.** Click currently exits before the group callback when `--version` is processed, so the guard does not fire for that flag. Should we make the exemption explicit in the skip list / documentation, in case click's behaviour changes?
- **Skip-list extensions.** Are there other commands that should join the skip list later? `skl deprecate` is one candidate (user might be marking a skill deprecated *because* of the version mismatch). `skl shared sync` is another (the very command that could fix the situation by pulling a newer kit). Currently both fire the guard.

Raised: 2026-05-17, during PR #5 review.

---

## Resolved

### ~~Q-001 - Drift severity in `skl validate`: warning or error?~~

The first `skl validate` PR treated `_shared/` drift relative to the manifest as a warning, not an error. Question was: should drift cause validate to fail (exit 1), or just warn?

Resolved by [SKL-001](decisions/SKL-001-drift-is-warning.md): drift is a warning. The spec language is "warns on divergent files"; drift is recoverable; the user fixes it on the next `skl shared sync`.

### ~~Q-002 - `skl validate --skill` / `--all`: silent no-op or "not yet implemented"?~~

Flags were accepted on the CLI (matching the spec) but no-oped with a stderr note. Question was: keep the silent no-op, or raise "not yet implemented"?

Resolved by [SKL-002](decisions/SKL-002-unimplemented-flags-error.md): unimplemented flags raise `NotImplementedError`, matching the convention used by unimplemented verbs.

### ~~Q-003 - Global `skl_version` compatibility guard: per-verb or every invocation?~~

`docs/spec/infrastructure.md` says `skl` should refuse to run if the installed version is outside the manifest's range, on every invocation. Initial validate PR scoped this to `skl validate` only. Question was: promote to a global CLI entry-point check?

Resolved by [SKL-003](decisions/SKL-003-global-compatibility-guard.md): yes, the guard fires at the top-level group callback for every subcommand inside a skill-host repo, with a small skip list (`init`, `validate`). Edge cases tracked separately as [Q-004](#q-004---global-skl_version-compatibility-guard-edge-cases).
