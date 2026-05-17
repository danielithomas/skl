# Changelog

All notable changes to `skl` are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

### Added
- Initial scaffold: package metadata, `--version`, click-based CLI surface with stub verbs.
- `docs/spec/` covering CLI surface, `skill-repo.yaml` manifest, infrastructure, values + secrets, and compilation.
- `docs/decisions/` covering D-007 (three-tier values), D-008 (secrets separation), D-009 (multi-repo architecture), D-010 (toolkit identity), D-011 (shared kit fetched).
- README opens with the `skl` vs `skillctl` distinction (per D-010 follow-up #8).
- CI workflow on push / PR: ruff lint + format check, pytest, CLI smoke.

### Status
- Pre-v0.1. The CLI surface is wired; verbs raise `NotImplementedError` with a pointer to the spec.

[Unreleased]: https://github.com/danielithomas/skl/compare/HEAD...HEAD
