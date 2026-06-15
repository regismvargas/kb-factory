# Smoke Tests

Fast structural checks that verify the repository and `.kb/` scaffold integrity.

## Checks

1. Root `.kb/` scaffold exists: kb.py, kb.config.json, SKILL.md, memory/, exports/, seed/
2. Project-base directories exist: core/, scaffolds/, migrations/, platforms/, examples/, tests/
3. `kb.py doctor --json` returns healthy status
4. Canonical template exists in `core/templates/kb/`

## When to Run

After every structural change to the repository.
