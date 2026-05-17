# SKL-002 - Unimplemented CLI flags raise "not yet implemented"

| Field | Value |
|-------|-------|
| **ID** | SKL-002 |
| **Date** | 17 May 2026 |
| **Status** | Final |
| **Owner** | Daniel Thomas |
| **Raised in** | PR #5 review |
| **Resolves** | [Q-002](../open-questions.md#q-002---skl-validate---skill----all-silent-no-op-or-not-yet-implemented) |

## Question

When a CLI flag is documented in the spec but not yet implemented (e.g. `skl validate --skill <name>` before per-skill validation lands), should `skl` silently accept-and-ignore the flag, or error out with "not yet implemented"?

## Decision

Error out. Unimplemented flags raise `NotImplementedError` and exit non-zero. The error message names the flag and points at `docs/spec/cli.md`.

## Rationale

- A silent no-op makes a user think the flag worked. They may write a script around it, run a CI job assuming it filtered by skill, and only discover the silence the day a real per-skill bug slips through.
- The cost of erroring is small: the user reads the message, drops the flag, gets the manifest-level check, and waits for the per-skill version to land.
- It mirrors the convention already in use elsewhere: every verb that has not been built raises `NotImplementedError` with a pointer to the spec. Flag-level NIE matches that pattern exactly - same error class, same `SPEC_REFERENCE` pointer.
- When a flag is eventually wired up, the NIE goes away in the same PR that implements the behaviour. There is no transitional "silently accept" phase to remove later.

## What this constrains in `skl`

- Any CLI flag that is documented in the spec but not yet implemented MUST raise `NotImplementedError` with a message including the flag name and the `SPEC_REFERENCE` pointer.
- New tests follow the existing "unimplemented verbs raise" pattern: invoke with `standalone_mode=False`, assert `isinstance(result.exception, NotImplementedError)`.
- Optional flags whose presence is purely advisory may be exempt - but in that case the flag should be removed from the CLI surface entirely, not preserved as a no-op.

## See also

- `docs/spec/cli.md` §`skl validate`
- `tests/test_cli.py::test_unimplemented_verbs_raise` (existing verb-level pattern)
- [Q-002](../open-questions.md#q-002---skl-validate---skill----all-silent-no-op-or-not-yet-implemented)
