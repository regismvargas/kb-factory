# Changelog

All notable changes to this project are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project aims to follow [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

This is the initial public open-source extraction of KB Factory from a private
authoring workspace. The release line is being prepared toward `1.0.0`.

### Added
- Apache-2.0 `LICENSE`, `NOTICE`, `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`,
  `SECURITY.md`, and this changelog.
- `ACKNOWLEDGMENTS.md` crediting design influences (Andrej Karpathy;
  Carlos Perez / @IntuitMachine).
- Documentation: competitive comparison, provenance & continuity notes, and a
  merit evaluation (`docs/`).

### Changed
- Removed internal/private references (cross-repo paths, a private compliance
  artifact, personal contact details) from the published tree.
- Neutralized internal-framework vocabulary in user-facing plugin documentation.

### Notes
- The core runtime is **standard-library only** (Python + SQLite); there are no
  third-party runtime dependencies.
- Knowledge is **append-only**: records are superseded, never silently
  overwritten.

<!-- On first tagged release, move the relevant items above under a dated
     "## [1.0.0] - YYYY-MM-DD" heading and reset Unreleased. -->
