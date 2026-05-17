# SKL-003 - Global `skl_version` compatibility guard at CLI entry

| Field | Value |
|-------|-------|
| **ID** | SKL-003 |
| **Date** | 17 May 2026 |
| **Status** | Final (edge cases tracked separately - see [Q-004](../open-questions.md#q-004---global-skl_version-compatibility-guard-edge-cases)) |
| **Owner** | Daniel Thomas |
| **Raised in** | PR #5 review |
| **Resolves** | [Q-003](../open-questions.md#q-003---global-skl_version-compatibility-guard-per-verb-or-every-invocation) |
| **Opens** | [Q-004](../open-questions.md#q-004---global-skl_version-compatibility-guard-edge-cases) |

## Question

`docs/spec/infrastructure.md` says `skl` should refuse to run if the installed version is outside the manifest's `skl_version` range, on every invocation. The first `skl validate` PR scoped the check to `skl validate` only. Should the check be promoted to a global guard that fires before any subcommand?

## Decision

Yes. The top-level CLI group callback (`skl.cli.main`) runs the compatibility check on every invocation made from inside a skill-host repo, with two exemptions:

- **`skl init`**: the global form creates a new repo (no existing manifest to check). When invoked inside an existing repo, init has its own "nested repo" handling that produces a more useful error.
- **`skl validate`**: explicitly designed to surface all validation issues including compatibility. Running the guard would short-circuit the report and hide other concurrent issues.

The skip list is exposed as `skl.cli.COMPAT_GUARD_SKIP` so it is discoverable and easy to test against.

The guard exits with code 4 per the spec, with a message naming the installed version and the manifest's range.

## Rationale

- Matches the spec language: "skl checks this on every invocation".
- Centralised in one place - individual verbs do not have to remember to call it. A future contributor adding `skl frobnicate` does not have to wire up a compatibility check; they get it for free.
- Two-command skip list is small enough to keep in mind. Adding a third entry requires a follow-up decision so the list does not silently grow.
- Lenient on parse failures: if the manifest is present but YAML-unparseable, the guard skips silently and lets `skl validate` surface the parse error. The alternative (fail at the guard with a "can't parse" message) would block every command on a broken manifest and obscure the actual problem.
- The guard reuses `_check_compatibility` from `skl.validate` via a thin `check_compatibility_or_message` wrapper, so the guard and validate's check 8 share their semver-range logic. No drift between the two paths.

## What this constrains in `skl`

- `skl.cli.main` is now decorated with `@click.pass_context`. The callback inspects `ctx.invoked_subcommand` against `COMPAT_GUARD_SKIP` and short-circuits with `ctx.exit(4)` on failure.
- `skl.validate.check_compatibility_or_message(repo_root)` is the canonical entry point for the guard. New code that needs an "is this skl compatible with the manifest" check should call it rather than re-implementing.
- Tests live in `tests/test_compat_guard.py`: verify the guard fires for non-exempt commands, skips for `init` / `validate`, tolerates unparseable / missing manifests, and silently passes when the installed version is in range.
- The skip list is part of the public CLI contract for now. Changing it requires a new SKL-NNN decision.

## Open follow-ups

Several edge cases need their own decisions before the guard's behaviour stabilises - tracked in [Q-004](../open-questions.md#q-004---global-skl_version-compatibility-guard-edge-cases):

- Whether to add an escape hatch (env var or flag).
- Whether unparseable-manifest handling should fail fast.
- Explicit `--version` exemption documentation.
- Possible additions to the skip list (`deprecate`, `shared sync`).

## See also

- `docs/spec/infrastructure.md` §Versioning
- `docs/decisions/D-010-toolkit-identity.md` (semver / version-range commitment)
- `docs/decisions/SKL-001-drift-is-warning.md` (similar separation of "hard fail" vs "recoverable" findings)
- [Q-003](../open-questions.md#q-003---global-skl_version-compatibility-guard-per-verb-or-every-invocation)
- [Q-004](../open-questions.md#q-004---global-skl_version-compatibility-guard-edge-cases)
