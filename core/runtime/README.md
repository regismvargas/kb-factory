# Runtime

This directory holds the first extracted runtime modules from `kb.py`.

## Extracted In Phase 1

- `constants.py`
- `paths.py`
- `config.py`
- `schema.py`
- `db.py`

These modules are mirrored into the shipped runtime locations under `.kb/runtime/`
and `core/templates/kb/runtime/` so `kb.py` can stay a thin local entrypoint
without introducing a second KB engine or changing install/deployment shape.

## Next Extractions

See `core/README.md` for the remaining split into records, search, exporters,
maintenance, doctor, and CLI wiring.

## Constraint

Every module here must remain stdlib-only.
