# SKL-001 - Shared-kit drift in `skl validate` is a warning, not an error

| Field | Value |
|-------|-------|
| **ID** | SKL-001 |
| **Date** | 17 May 2026 |
| **Status** | Final |
| **Owner** | Daniel Thomas |
| **Raised in** | PR #5 review |
| **Resolves** | [Q-001](../open-questions.md#q-001---drift-severity-in-skl-validate-warning-or-error) |

## Question

When `skl validate` finds that `_shared/.kit_version` does not match `shared_kit.version` in the manifest, should that fail validation (exit 1) or just warn?

## Decision

Warning. `skl validate` exits 0 (with a "validation ok (with warnings)" summary line) when the only finding is drift; it does not promote drift into the error stream.

## Rationale

- The spec language is "warns on divergent files" - we follow it literally.
- A drifted `_shared/` is a recoverable state: the user runs `skl shared sync` and it is fixed. Failing validate would block downstream commands (compile, deploy) on a non-blocking condition.
- The "scaffold offline" path that [SKL-002 in the parent project](../../README.md) explicitly supports also creates a manifest where `version: "latest"` is unresolved. Treating that as an error would force a `skl shared sync` to make validate green, conflicting with the offline-scaffolding posture.
- Schema and compatibility failures are different - they indicate a manifest that should not be acted on. Drift just means the kit on disk is older / newer than what is pinned; the rest of the manifest is still trustworthy.

## What this constrains in `skl`

- `skl.validate._check_shared_kit_drift` accumulates `warnings` only, never `errors`. The dedicated test `test_drift_warns_when_versions_diverge` (etc.) asserts this property.
- The CLI summary line distinguishes "validation ok" from "validation ok (with warnings)" so the user can tell warnings are present without exit-code noise.

## See also

- `docs/spec/cli.md` §`skl validate`
- `docs/spec/compilation.md` §Validators (Shared-kit drift)
- [Q-001](../open-questions.md#q-001---drift-severity-in-skl-validate-warning-or-error)
