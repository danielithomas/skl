# SKL-009 - M365 declarative-agent schema versioning: per-skill pin, multi-version kit

| Field | Value |
|-------|-------|
| **ID** | SKL-009 |
| **Date** | 21 May 2026 |
| **Status** | Final |
| **Owner** | Daniel Thomas |
| **Raised in** | [`docs/analysis/skills-spec.md`](../analysis/skills-spec.md) §9 (risks table, M365 row) |
| **Resolves** | [Q-012](../open-questions.md#q-012---m365-declarative-agent-schema-versioning-how-do-we-track-microsofts-iteration) |
| **Builds on** | [SKL-004](./SKL-004-master-skill-md-posture.md), [D-011](./D-011-shared-kit-fetched.md) |

## Question

The Microsoft 365 declarative-agent manifest schema has moved from v1.3 to v1.7 in approximately six months (page updated 14 May 2026 - roughly one minor version per six weeks). Each release adds capabilities; some changes are additive but at least the editorial-answers and worker-agents surfaces represent new field shapes Microsoft's validator enforces.

We need a strategy that handles:

- Compile reproducibility across `skl shared sync` events.
- A skill adopting new schema features without forcing a fleet-wide migration.
- Microsoft retiring older schema versions on their platform.
- The relationship between Microsoft's release cadence and `skl`'s own semver.

Sub-questions from Q-012:

1. Bundle the JSON schema in the kit and pin per skill, or always emit the latest known?
2. How does `skl validate` handle a skill written for a schema version not in the bundled kit?
3. When v1.8 lands, is that a minor or major `skl` bump?

[SKL-004](./SKL-004-master-skill-md-posture.md) already settled that per-platform content lives in `skl/platforms/m365.yaml` sidecars; the SKL-004 example included `schema_version: "1.7"` as a placeholder pin. This decision makes that pinning load-bearing.

## Decision

Three pieces:

**1. Per-skill pin in the M365 sidecar is authoritative.**

`skl/platforms/m365.yaml` declares `schema_version: "1.7"` (or whichever version the skill targets). The pin is mandatory when the sidecar exists - omitting it is a validate error, not an implicit "use the kit default" signal. `skl init` and the future `skl add-platform m365` scaffold the pin from the kit's current default, so the author does not pick on a blank-page initial creation; from that point the pin in the sidecar is the source of truth.

Compile is deterministic across `skl shared sync` boundaries. Updating the kit does not silently shift the schema version any existing skill compiles to; only an explicit pin change in the sidecar moves a skill to a new version.

**2. The bundled kit ships multiple supported schema versions side by side.**

Layout:

```
_shared/schemas/
├── skill.frontmatter.schema.json                    # owned by skl (SKL-004)
└── platforms/
    ├── copilot-studio.schema.json                   # sidecar input schemas, owned by skl
    ├── m365.schema.json
    ├── vscode.schema.json
    └── m365/                                        # compiled-output schemas, Microsoft-owned
        ├── declarative-agent-manifest-1.5.json
        ├── declarative-agent-manifest-1.6.json
        ├── declarative-agent-manifest-1.7.json
        └── index.json
```

`index.json` shape:

```json
{
  "default": "1.7",
  "supported": ["1.5", "1.6", "1.7"],
  "deprecated": [
    { "version": "1.5", "note": "Microsoft retires v1.5 after 2026-09-01; migrate before then" }
  ]
}
```

The kit ships whichever supported set keeps active skills compiling. Older versions get removed from new kit releases only after a runway in which they appear in `deprecated[]` with a note. The `default` is what fresh-skill scaffolds adopt; it has no effect on existing skills.

Two schemas per platform live cleanly side by side under this layout:

- **Sidecar input schema** at `_shared/schemas/platforms/m365.schema.json` - what the author may declare in `skl/platforms/m365.yaml`. Owned by `skl`; revised when SKL-NNN decisions change the sidecar shape.
- **Compiled output schemas** at `_shared/schemas/platforms/m365/declarative-agent-manifest-<v>.json` - the Microsoft schema, multi-versioned. Owned by Microsoft; bundled here from upstream.

**3. `skl validate` resolution.**

For a skill whose `skl/platforms/m365.yaml` declares `schema_version: "1.7"`:

1. Validate the sidecar against `_shared/schemas/platforms/m365.schema.json` (sidecar shape).
2. Resolve the manifest schema from `_shared/schemas/platforms/m365/declarative-agent-manifest-1.7.json`.
3. If `platforms/m365/declarative-agent.json` exists, validate it against the resolved schema.

Resolution outcomes:

| Sidecar pin state | `skl validate` behaviour |
|---|---|
| Pin matches a supported, non-deprecated version | Pass silently |
| Pin matches a `deprecated[]` entry | Pass with a strong warning carrying the deprecation note |
| Pin matches no version in the kit (older than the kit's earliest, or newer than its latest) | **Error**, exit 1. Message lists supported versions and suggests `skl shared sync` |
| Pin older than the kit's `default` but still supported | Pass with a soft "newer schema available" warning |
| Sidecar exists but lacks `schema_version` | Error - mandatory field missing |

Soft warnings follow [SKL-001](./SKL-001-drift-is-warning.md)'s drift-is-warning posture; errors are reserved for cases where the compile genuinely cannot proceed correctly.

**4. `skl`'s semver and M365 schema iteration are decoupled.**

M365 schema releases are kit-level events delivered through `skl shared sync`. They do not require an `skl` version bump on their own. `skl`'s semver moves only when:

- The sidecar input schema (`m365.schema.json`) gains a breaking change.
- The compiler emits a different artefact shape (e.g. a structural change to how `instructions` is composed).
- `skl` drops support for a schema version that some still-active skills pin to, without a deprecation runway in `index.json` - this is the only path to a major bump triggered by M365 specifically, and is reserved for the unusual case where Microsoft retires a version faster than we can ship a runway.

In the normal flow: Microsoft releases v1.8, `ai-skills-shared` ships a kit update that adds `declarative-agent-manifest-1.8.json` and moves `default` to `1.8`. Skill-host repos run `skl shared sync` at their own pace and decide per skill whether to repin. `skl`'s own version is unchanged.

## Rationale

**Why per-skill pinning over always-latest.**

Compile is documented as deterministic in `docs/spec/compilation.md`: "same input produces byte-identical output". Always-latest breaks that property the moment a `skl shared sync` runs - the schema version of the output silently shifts. Reproducibility is load-bearing for the `platforms/` commit-the-artefacts model (per D-001): reviewers comparing `git log -p platforms/m365/` should see only the changes the author intended, not the schema iteration on top.

Per-skill pinning is also the only way a single skill-host repo can carry skills targeting different M365 schema versions during a migration. Without it, the repo has to migrate atomically; with it, the repo migrates one skill at a time on its own schedule.

**Why mandatory pin rather than optional.**

Optional pin with kit-default fallback (Strategy C in the walkthrough) reintroduces the determinism gap for any skill that lacks an explicit pin. Mandatory pin means there is exactly one source of truth - the sidecar - and no resolution branch. The ergonomic cost is zero because `skl init` and the platform-add scaffold write the pin automatically.

**Why ship multiple schema versions in the kit rather than only the current.**

Three reasons:

- Kit bytes are cheap; a typical JSON schema is small (tens of KB).
- It lets skills migrate on their own timeline rather than synchronously when the kit refreshes.
- It supports the deprecation runway: Microsoft retiring a version on their platform is a known event with timing, not a `skl` event with timing. The `deprecated[]` array in `index.json` communicates this to validate without forcing the kit author to delete the schema file the same day.

Removing a schema from the kit only happens after it has lived in `deprecated[]` long enough for active skills to migrate.

**Why M365 schema iteration is not an `skl` versioning event.**

`docs/spec/infrastructure.md` defines major bumps in terms of breaking changes to "the compiler output contract for any enabled platform". The contract is a function of (a) what the compiler emits given (b) what the sidecar declares. With per-skill pinning, the output contract is `(sidecar input, pinned schema version)` - and updating the kit to ship a new schema version does not change the output of any existing pinned skill. The contract holds.

Coupling `skl`'s semver to Microsoft's schema cadence would force a major `skl` release every ~6 weeks for no actual user-visible breakage. Decoupling them lets `skl`'s version reflect changes users actually need to know about.

The exception - dropping a still-pinned schema version without runway - is theoretical and we control whether it happens. The runway mechanism (deprecation note in `index.json`) is cheap to provide; the only scenario where we cannot provide it is if Microsoft retires a version faster than we can ship a kit update with a deprecation note, which is implausible for an entire active version.

**Why hard error on missing pin version rather than soft fallback.**

Falling back to the nearest available schema risks silent semantic drift - the compiled artefact validates against a schema the author didn't write for. Hard error with an actionable message (`run skl shared sync; or pin to one of the supported versions`) gives the author clear next steps and surfaces the kit/skill mismatch cleanly.

## What this constrains in `skl`

- The bundled kit layout under `_shared/schemas/platforms/m365/` is fixed by this decision: one schema file per version, plus `index.json` declaring `default`, `supported[]`, `deprecated[]`. Kit authors (`ai-skills-shared`) follow this convention.
- `_shared/schemas/platforms/m365.schema.json` makes `schema_version` a **required** top-level field. The same SKL-004 schema for the M365 sidecar gains this requirement.
- `skl init` and the future `skl add-platform m365` read `_shared/schemas/platforms/m365/index.json` `default` and scaffold `schema_version: "<default>"` into the new sidecar.
- `skl validate` resolves the sidecar's pinned schema version against `_shared/schemas/platforms/m365/declarative-agent-manifest-<version>.json`. The resolution outcomes above are the contract.
- `skl shared sync` (per D-011) is the channel through which new schema versions arrive. The kit update is an additive change for existing skills (their pins continue to resolve); only fresh scaffolds pick up the new `default`.
- The M365 compiler writes `version: "<pinned-version>"` into the compiled `declarative-agent.json` `version` field. The pin and the manifest's own `version` field are kept in sync.
- `skl validate` warnings:
  - Pin older than kit `default`: soft warning ("v1.6 is supported; v1.7 is current").
  - Pin in `deprecated[]`: strong warning carrying the deprecation note verbatim.
  - Sidecar missing `schema_version`: error.
  - Pin not found in kit: error.
- This decision does **not** constrain how the same pattern applies to other fast-iterating Microsoft schemas if they appear (Copilot Studio metadata format, Teams app manifest, etc.). The convention extends naturally - per-platform subfolder, version files, `index.json` - but is committed to in a future decision when those needs are real.
- `docs/spec/compilation.md` M365 section and `docs/spec/infrastructure.md` versioning section are updated to point to this decision.

## See also

- [`docs/analysis/skills-spec.md`](../analysis/skills-spec.md) §4.6 (M365 schema surface), §8.4 (M365 compile mapping), §9 (risks table).
- [`SKL-004`](./SKL-004-master-skill-md-posture.md) - per-platform sidecars; the M365 schema example included a `schema_version` placeholder this decision makes load-bearing.
- [`SKL-001`](./SKL-001-drift-is-warning.md) - drift-is-warning posture this decision applies to the older-pin-than-default case.
- [`D-011`](./D-011-shared-kit-fetched.md) - `_shared/` distribution mechanism; bundled M365 schemas arrive through this channel.
- [`docs/spec/compilation.md`](../spec/compilation.md) - M365 compiler description, to be updated for the schema-version pin.
- [`docs/spec/infrastructure.md`](../spec/infrastructure.md) - `skl` semver policy; this decision clarifies that bundled-platform-schema iteration is a kit event, not an `skl` event.
