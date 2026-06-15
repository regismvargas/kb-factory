# Core

The shared KB runtime and canonical template.

## What core/ owns

- `templates/kb/` — the canonical scaffold snapshot that every new project receives
- `runtime/` — future home of modularized kb.py (Phase 2)

## Modularization Roadmap

The current `kb.py` is a ~850-line monolith that handles config, schema, CRUD, search, export, maintenance, and CLI parsing. It works correctly and its CLI surface is the compatibility contract.

Phase 2 will extract it into:

| Module | Responsibility |
|--------|---------------|
| `config.py` | Read and validate `kb.config.json` |
| `paths.py` | Resolve `KB_ROOT`, DB, and derived directories |
| `schema.py` | Bootstrap and schema versioning |
| `db.py` | SQLite connection, WAL, transaction helpers |
| `records.py` | Create, get, update, supersede, resolve |
| `search.py` | FTS5 and filters |
| `seed.py` | Bulk import and fixtures |
| `exporters.py` | NOW, HOT, INDEX, topics, PROJECT_PACK |
| `maintenance.py` | audit-tiers and consolidate |
| `doctor.py` | Integrity, schema, invariants |
| `cli.py` | Parser and command wiring |

The delivered `kb.py` remains a thin entrypoint. External behavior stays identical.

## Rules

- `core/` never depends on `scaffolds/`, `migrations/`, or `platforms/`
- `core/templates/kb/` is the single source for scaffold generation
- Internal modularization must not break the `kb.py` CLI surface
