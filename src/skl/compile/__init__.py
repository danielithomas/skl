"""Compile a SKILL.md (+ sidecars) to one or more platform artefacts.

Public surface:

- :func:`build_ir(skill_root, repo_root)` - parse SKILL.md + sidecars into a
  :class:`ResolvedSkill` IR. The IR is shared by all per-platform compilers
  for one skill.
- :func:`compile_skill(ir, platform_id)` - dispatch a single (skill, platform)
  pair to the matching compiler and write the artefact under
  ``<repo_root>/platforms/<platform>/<skill>/``.
- :class:`CompileResult` / :class:`CompilerNotImplementedError` - return /
  error types.

Compilers covered as of Stage 4:

- ``claude-code``, ``claude-cowork``, ``ms-cowork`` - Skills-native targets
  (Stage 2). Output bytes are byte-identical across the three.
- ``vscode`` - emits Skill variant and/or Custom Agent variant per SKL-007
  (Stage 3).
- ``copilot-studio`` - Copilot Studio instructions field (8K-budget hard
  cap, canonical-section composition with Identity surfaced,
  knowledge/tools tokens rewritten to ``/<binding>`` references). See
  :mod:`skl.compile.copilot_studio`.
- ``m365`` - declarative-agent manifest + instructions per SKL-009.
  Schema-version pin mandatory; schema resolution via the kit's
  ``index.json``; compiled manifest validated against the per-version
  schema before write. 8K hard budget on the instructions field. See
  :mod:`skl.compile.m365`.

All six v0.1 platforms now compile. :class:`CompilerNotImplementedError`
is no longer raised for any of them; the class remains for future
deferred targets.
"""

from __future__ import annotations

from skl.compile.budget import BudgetExceededError
from skl.compile.copilot_studio import COPILOT_STUDIO_PLATFORM, compile_copilot_studio
from skl.compile.ir import CompileResult, ResolvedSkill, build_ir
from skl.compile.m365 import M365_PLATFORM, M365SchemaError, compile_m365
from skl.compile.provenance import provenance_comment
from skl.compile.skills_native import SKILLS_NATIVE_PLATFORMS, compile_skills_native
from skl.compile.vscode import VSCODE_PLATFORM, compile_vscode

__all__ = [
    "BudgetExceededError",
    "CompileResult",
    "CompilerNotImplementedError",
    "M365SchemaError",
    "ResolvedSkill",
    "build_ir",
    "compile_skill",
    "provenance_comment",
]


class CompilerNotImplementedError(NotImplementedError):
    """Raised when a known platform's compiler has not landed yet.

    Distinct from ``ValueError`` (unknown platform) so the CLI can map it
    to a clearer message and exit code.
    """


def compile_skill(ir: ResolvedSkill, platform_id: str) -> CompileResult:
    """Dispatch one (skill, platform) pair to its compiler.

    Skills-native targets (claude-code / claude-cowork / ms-cowork) share
    :func:`compile_skills_native`. VS Code routes to :func:`compile_vscode`
    (may emit two variants per SKL-007). Copilot Studio and M365 raise
    :class:`CompilerNotImplementedError` pending Stage 4.
    """
    if platform_id in SKILLS_NATIVE_PLATFORMS:
        return compile_skills_native(ir, platform_id)
    if platform_id == VSCODE_PLATFORM:
        return compile_vscode(ir)
    if platform_id == COPILOT_STUDIO_PLATFORM:
        return compile_copilot_studio(ir)
    if platform_id == M365_PLATFORM:
        return compile_m365(ir)
    raise ValueError(f"unknown platform {platform_id!r}")
