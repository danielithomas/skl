# SKL-010 - Compatibility guard edge cases: env-var escape hatch, fail-fast on parse failure, skip list unchanged

| Field | Value |
|-------|-------|
| **ID** | SKL-010 |
| **Date** | 21 May 2026 |
| **Status** | Final |
| **Owner** | Daniel Thomas |
| **Raised in** | PR #5 review (Q-004) |
| **Resolves** | [Q-004](../open-questions.md#q-004---global-skl_version-compatibility-guard-edge-cases) |
| **Builds on** | [SKL-003](./SKL-003-global-compatibility-guard.md) |

## Question

[SKL-003](./SKL-003-global-compatibility-guard.md) landed a global `skl_version` compatibility guard at the CLI entry, with skip list `{init, validate}`, exit code 4 on version-range failure, and silent skip when the manifest is YAML-unparseable. SKL-003 explicitly deferred four edge cases as Q-004:

1. Should there be an escape hatch (env var or flag) for emergency cases where a user needs to run one command despite a version mismatch?
2. Should unparseable-manifest behaviour change from silent skip to fail-fast?
3. Should the click eager-exit behaviour for `--version` and `--help` be made explicit?
4. Should `skl deprecate` or `skl shared sync` join the skip list?

## Decision

Four pieces.

**1. Escape hatch: `SKL_IGNORE_COMPAT=1` env var only.**

When `SKL_IGNORE_COMPAT` is set to any truthy value (`1`, `true`, `yes`, case-insensitive), the guard's version-range check is bypassed. Every command run with the env var set emits a stderr warning, even when the command would have passed the check anyway:

```
compatibility guard bypassed via SKL_IGNORE_COMPAT (installed skl 0.3.1; manifest pins >=0.4,<0.5)
```

The bypass is loud by design. Users should feel slightly worse about reaching for it than typing the command would suggest.

No `--ignore-compat` flag in v0.x. A flag is easier to bake into Makefiles and CI scripts; the env var stays with the session and shows up in shell history. If real-world evidence shows users wanting the flag form, we revisit in v0.2.

The env var bypasses the **version-range check only**. It does not bypass parse failure (see piece 2), missing-manifest detection (which already no-ops), or any other validation.

**2. Unparseable manifest: fail fast.**

The guard reads the manifest before checking version compatibility. If the YAML cannot be parsed, the guard exits 4 with a message pointing at `skl validate`:

```
skill-repo.yaml could not be parsed; run `skl validate` to see the parse error.
```

Exit code 4 is reused (the compatibility check could not pass; the message explains why). `init` and `validate` remain in the skip list so the user has a path to diagnose the parse error. Every other command blocks until the YAML parses.

This supersedes SKL-003's silent-skip behaviour. Reason: every downstream command that depends on the manifest will fail somewhere weirder; clear fail-fast with an actionable next step is better UX than a confusing downstream error.

`SKL_IGNORE_COMPAT` does **not** bypass parse failure. The escape hatch is for "I know my version is wrong but I'll fix it later"; parse failure is "the file is broken". Different category, different fix.

**3. `--version` / `--help` exemption: documented, not coded.**

Click's `@click.version_option` and the implicit `--help` are both eager options that exit before the group callback fires. The guard never runs for either, which is correct behaviour - showing version or help should never error on compat mismatch.

This is documented in a code comment on `skl.cli.main` and named explicitly in this decision. The `COMPAT_GUARD_SKIP` skip list is keyed on `ctx.invoked_subcommand`, but `--version` and `--help` are flags, not subcommands - adding them to the skip list would be misleading.

If Click's eager-exit behaviour ever changes (unlikely; would be a backwards-incompatible Click change), the guard gains an explicit short-circuit for `--version` / `--help`. Until then, no belt-and-braces code.

**4. Skip list stays `{init, validate}`.**

Neither `skl deprecate` nor `skl shared sync` is added.

- `skl deprecate` writes to source (modifies SKILL.md frontmatter to add `status: deprecated`). That's a real change that benefits from running on a compatible `skl`. The "I'm migrating off the old version" workflow is served by `SKL_IGNORE_COMPAT`.
- `skl shared sync` is destructive (overwrites `_shared/`). Silently bypassing the guard so the user can run a destructive command is the opposite of safe. The catch-22 it might solve (syncing a newer kit relaxes the version range) is reachable via `SKL_IGNORE_COMPAT`, with a clear warning.

When `skl init` lands its repo-scoped form (currently deferred), it stays in the skip list - or, more precisely, the skip list applies to the global form, and the repo-scoped form gains its own decision then. Not in scope here.

## Rationale

**Why env var, not flag.**

The env var is harder to make permanent by accident. Flags get baked into shell aliases and Makefiles; env vars stay in shell history and show up in process listings. The escape hatch should leave a trail, and a noisy bypass warning every time it runs is part of that trail. A flag is friendlier in `--help` but friendliness is not the goal here.

The flag form remains available as a v0.2 addition if authored evidence shows real demand. Adding it later costs nothing; removing it once shipped would be a breaking change.

**Why loud bypass.**

A silent escape hatch is a backdoor. Users who set `SKL_IGNORE_COMPAT=1` in their shell rc to "stop the noise" lose the protection of the guard entirely. The warning on every bypassed command keeps the protection cost-aware. If the warning is annoying, that's the signal to fix the version range, not to ignore the warning harder.

**Why fail-fast on parse failure rather than silent skip.**

SKL-003's silent-skip posture was conservative - it acknowledged that the guard could not assess compatibility on a broken manifest and chose to defer to `skl validate`. Six months of "what does this command actually do?" reasoning later, the failure modes look worse than the cost: a user running `skl compile` on a broken manifest gets a downstream error that doesn't mention the manifest. Fail-fast at the guard with a direct pointer to `skl validate` is shorter and clearer.

The parse-error message is informational only - it does not try to surface the actual YAML parse error. That's `skl validate`'s job. The guard's message is "you have a parse error; here is how to see it". Splitting the concern keeps the guard small.

**Why `SKL_IGNORE_COMPAT` does not bypass parse failure.**

These are different failure categories. Version mismatch is "the tool and the repo disagree on which `skl` to use" - debatable, sometimes the user is right. Parse failure is "the file cannot be read" - not debatable, the file is broken. Bypassing parse failure means the user is asking us to run on a corrupted manifest. That's not an emergency override, that's working around symptoms. We don't ship that capability.

**Why decline the skip-list extensions.**

Both candidates were raised in Q-004 with reasoning. `deprecate` is a "fix a content issue" command; running it on the wrong `skl` doesn't help fix the version mismatch. `shared sync` could in theory relax the version range, but only if the kit update happens to relax it - and running a destructive sync on the wrong `skl` to maybe fix a version issue is upside-down.

The escape hatch covers both cases with a single mechanism. Adding skip-list entries duplicates that coverage with surface area (each addition is a new behaviour to test, document, and reason about). Single mechanism is cleaner.

**Why document the click eager-exit assumption rather than coding around it.**

Click's eager-option behaviour for `--version` and `--help` is stable and documented. The probability of it changing in a way that breaks our guard is low; the cost of a defensive short-circuit is small but ongoing (more code to read, one more thing to mentally execute when reading the guard). The right balance is to name the assumption clearly in the code comment and the decision, so a future Click upgrade that breaks the assumption surfaces in tests and someone reads the comment and adds the short-circuit then.

## What this constrains in `skl`

Implementation deltas this decision authorises (lands in a follow-up code PR):

- `skl.cli.main` reads `os.environ.get("SKL_IGNORE_COMPAT")`. If set to a truthy value, the guard checks compatibility for diagnostics only and emits the bypass warning to stderr, then returns without exiting. The check still runs so the warning carries the actual installed-vs-pinned versions.
- `check_compatibility_or_message` (in `skl.validate`) gains an additional return state distinguishing "version mismatch" from "manifest unparseable". The guard maps the two states to different stderr messages but the same exit code (4).
- The current silent-skip-on-parse-failure code path is removed. The guard exits 4 with the parse-failure message when the manifest is present but unparseable.
- `skl.cli.main`'s docstring is updated to name the `--version` / `--help` exemption and reference this decision.
- `tests/test_compat_guard.py` gains cases for: (a) env var bypass emits warning and lets the command run; (b) env var does not bypass parse failure; (c) parse failure exits 4 with the parse-failure message; (d) parse-failure exit code is reached via every non-exempt subcommand.
- `docs/spec/infrastructure.md` versioning section gains a paragraph documenting `SKL_IGNORE_COMPAT` and the parse-failure fail-fast.
- `COMPAT_GUARD_SKIP` remains `frozenset({"init", "validate"})`. Adding a third entry continues to require a new SKL-NNN decision.

This decision does **not** authorise adding `--ignore-compat` as a CLI flag. That requires a follow-up decision if the env var form turns out to be insufficient.

## See also

- [`SKL-003`](./SKL-003-global-compatibility-guard.md) - the guard's original landing; this decision closes its deferred edge cases.
- [`docs/spec/infrastructure.md`](../spec/infrastructure.md) §Versioning - to be updated for the env var and parse-fail behaviour.
- [`tests/test_compat_guard.py`](../../tests/test_compat_guard.py) - existing test surface for the guard; expanded by the implementation PR.
