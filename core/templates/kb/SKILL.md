# KB Skill

Use this skill when the project has a `.kb/` directory and you need persistent context.

## Session start

Use the bootstrap mode that matches the session purpose. When in doubt, start thin.

### Thin bootstrap (default)

1. Run `python .kb/kb.py lifecycle session-start --json`.
2. Read `.kb/memory/NOW.md`.
3. Stop. Load richer context only when the conversation demands it.

### Standard bootstrap (when the active working set is clearly needed)

1. Run `python .kb/kb.py lifecycle session-start --json`.
2. Read `.kb/memory/NOW.md`.
3. Read `.kb/memory/HOT.md`.
4. Search or check pending as needed.

### Deep review bootstrap (audit, close-out, or review sessions only)

1. Run `python .kb/kb.py lifecycle session-start --json`.
2. Read `.kb/memory/NOW.md`.
3. Read `.kb/memory/HOT.md`.
4. Read `.kb/memory/INDEX.md`.
5. Load additional surfaces as needed for the review scope.

### On-demand loading (all modes)

These surfaces are always available but not preloaded:

- `.kb/memory/HOT.md` — current working set
- `.kb/memory/INDEX.md` — broader KB map
- `python .kb/kb.py search "<term>"` — search before assuming
- `python .kb/kb.py pending` — open pendencias

## During the session

1. Record only durable and non-derivable knowledge.
2. Use the canonical categories:
   - `DECISAO`
   - `PREMISSA`
   - `FATO`
   - `PENDENCIA`
   - `APRENDIZADO`
3. Use `update` only for routing metadata such as tier, review date, or tags.
4. If meaning changed, use `supersede`, not `update`.
5. Re-check sensitive facts against the current source before relying on them.

## End of session

1. Run `python .kb/kb.py lifecycle session-end --json`.
2. If HOT overflow or semantic hygiene is in scope, run read-only `python .kb/kb.py hygiene-audit --json`.
3. If stale HOT items should really fall back, run `python .kb/kb.py lifecycle scheduled-maintenance --apply-demotions --json`.
4. If schema or search feels wrong, run `python .kb/kb.py doctor --json`.

## Anti-patterns

1. Do not dump transcripts or large raw logs into the curated memory layer.
2. Do not promote everything to `HOT`.
3. Do not treat the KB as infallible truth.
4. Do not skip consolidation once duplicates or stale premises appear.
5. Do not auto-demote HOT records from semantic judgment alone.
