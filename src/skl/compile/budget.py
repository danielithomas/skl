"""Per-platform character budgets enforced at compile time.

Source of truth for the v0.1 hard caps:

| Platform        | Cap       | Source of truth                           |
|-----------------|-----------|-------------------------------------------|
| copilot-studio  | 8,000     | Copilot Studio instructions field hard cap|
| m365            | 8,000     | M365 declarative-agent ``instructions``   |

The Skills-native and VS Code targets have no hard cap; only the
Microsoft compilers enforce a budget.

Per-skill overrides live in the platform sidecar's ``budget:`` field
(Copilot Studio sidecar; M365 schema does not currently surface this -
edit here when it does).

:func:`enforce_budget` raises :class:`BudgetExceededError`; the CLI
maps that to exit code 1 with a human-readable error.
"""

from __future__ import annotations

PLATFORM_BUDGETS: dict[str, int] = {
    "copilot-studio": 8000,
    "m365": 8000,
}


class BudgetExceededError(ValueError):
    """The compiled artefact exceeds the platform's hard character cap."""


def enforce_budget(
    text: str,
    *,
    platform_id: str,
    skill_name: str,
    override: int | None = None,
) -> None:
    """Verify ``text`` fits within the platform's hard cap.

    ``override`` (if not None) replaces the default cap from
    :data:`PLATFORM_BUDGETS`. Useful for the Copilot Studio sidecar's
    per-skill ``budget:`` field.

    Raises :class:`BudgetExceededError` when the text exceeds the cap.
    Silently passes when there is no cap configured for ``platform_id``.
    """
    cap = override if override is not None else PLATFORM_BUDGETS.get(platform_id)
    if cap is None:
        return
    actual = len(text)
    if actual > cap:
        raise BudgetExceededError(
            f"{skill_name} ({platform_id}): compiled instructions are "
            f"{actual:,} chars; the {platform_id} cap is {cap:,}. "
            "Trim the source SKILL.md or set a higher per-skill `budget` "
            "in the sidecar where the platform schema allows."
        )
