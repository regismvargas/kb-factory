# Tests

## Test Categories

### Smoke Structure Checks (`smoke/`)

Verify that the repository structure and `.kb/` scaffold are intact after changes.

These are fast, filesystem-level checks:
- Required directories exist
- Required files exist
- `.kb/` scaffold is complete (kb.py, kb.config.json, SKILL.md, memory/, exports/, seed/)
- `kb.py doctor` passes

Run after every structural change to the repo.

### Compatibility Checks (future)

Verify that the `.kb/` contract is preserved across changes to the core runtime.

These are behavioral checks:
- `kb.py init` creates a valid database
- `kb.py bulk-import` accepts canonical seed format
- `kb.py export` generates `NOW.md`, `HOT.md`, `INDEX.md`, and topics
- `kb.py doctor --json` returns healthy status
- `kb.py search` returns expected results from seeded data
- FTS5 index is functional
- Supersede preserves audit trail
- Tier changes are logged

These will be implemented when `core/runtime/` modularization begins (Phase 2). They ensure that the modularized runtime maintains behavioral equivalence with the monolithic `kb.py`.

## Running Tests

Smoke checks can be run with the verification commands from `dispatch/WP-KBF.01_VERIFICATION_SPEC.json`.
