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

Compilers covered as of Stage 3:

- ``claude-code``, ``claude-cowork``, ``ms-cowork`` - Skills-native targets
  (Stage 2). All three share one implementation in
  :mod:`skl.compile.skills_native`; output bytes are byte-identical across
  the three, only the output path differs. Frontmatter ``skl:`` block
  stripped (SKL-006); ``## Identity`` body section stripped (SKL-008);
  top-line provenance comment per SKL-006.
- ``vscode`` - emits one or both of a Skill variant (Skills-native bytes,
  written to ``platforms/vscode/skill/<name>/``) and a Custom Agent variant
  (``platforms/vscode/agent/<name>.agent.md``). Gated by the
  ``skl/platforms/vscode.yaml`` sidecar per SKL-007.

Copilot Studio / M365 (Stage 4) still raise :class:`CompilerNotImplementedError`.
"""

from __future__ import annotations

from skl.compile.ir import CompileResult, ResolvedSkill, build_ir
from skl.compile.provenance import provenance_comment
from skl.compile.skills_native import SKILLS_NATIVE_PLATFORMS, compile_skills_native
from skl.compile.vscode import VSCODE_PLATFORM, compile_vscode

__all__ = [
    "CompileResult",
    "CompilerNotImplementedError",
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
    if platform_id in {"copilot-studio", "m365"}:
        raise CompilerNotImplementedError(f"compiler for {platform_id!r} lands in Stage 4")
    raise ValueError(f"unknown platform {platform_id!r}")
