# Provenance & continuity

This document explains **how KB Factory keeps memory continuous** across
conversations within a project and across agents in a workflow, and records the
**implementation status** of that machinery. It feeds the user-facing
[concepts.md](concepts.md) and the developer-facing [architecture.md](architecture.md).

## The continuity guarantee

The need KB Factory serves: *decisions, premises, facts, status, open items, and
learnings should survive between conversations within a project, and be shared
across agents in a multi-agent workflow* — without re-explaining context every
session and without trusting un-auditable chat scrollback.

KB Factory delivers this through a single canonical store plus a governed
lineage from raw input to every surface an agent reads:

```
source  →  record  →  { wiki page | export / context pack | session surface }
   │          │                         │
   │          │                         └─ what an agent loads at session start
   │          └─ canonical, typed, versioned (SQLite + FTS5)
   └─ raw immutable input (ingested, hashed)
```

- **One project = one KB.** Continuity is *project-scoped*, so every
  conversation and every agent in that project reads the same canonical memory.
- **Typed records, not chat history.** Knowledge is filed as
  decision / premise / fact / open-item / learning — queryable and auditable.
- **Supersession, never overwrite.** When meaning changes, the old record is
  superseded and retained; the audit trail is preserved.
- **Thin session surface.** Each session starts from `NOW.md` (and `HOT.md` on
  demand), so continuity is cheap in tokens.
- **Operation log.** Mutations append to an operations log, so "who changed
  what, when, and why" is reconstructable.

For multi-agent workflows, the same canonical `.kb/` is the shared substrate:
agents file and read records through the CLI, so a learning captured by one
agent is immediately available — and attributable — to the next.

## Implementation status

| Claim | Evidence | Status |
|---|---|---|
| Provenance is specified, covering transformations not just source IDs | the project's provenance-chain specification | ✅ Specified |
| Required manifest fields exist for every generated surface (output id, activity, actor, input records/sources, stale warnings, validation status, tool) | Spec §"Required Manifest Fields" | ✅ Specified |
| The runtime implements manifests / proposals / `operations.jsonl` / `proposal-apply` | extensive references across the runtime's manifest/proposal machinery | ✅ Implemented in code |
| Canonical records support supersession + source linkage | `core/runtime/records.py` (supersede / `supersedes_id` / `source`) | ✅ Implemented in code |
| End-to-end lineage is *demonstrably* intact via a live run (ingest → file → export → trace back) | not yet executed in this pass | ⏳ Pending demo |

**Honest gap:** the chain is *specified* and *implemented*, but it has been
verified by reading the spec and code — not yet by executing a full
ingest→record→export→session round-trip and tracing a surface back to its
sources. That live demonstration is the remaining acceptance step (see the gap
list below and the [comparison](comparison.md)).

## Gap list → backlog

1. **Run a reproducible end-to-end provenance demo** and capture it (a short
   transcript or test) so the continuity claim is shown, not just asserted.
2. **Document the cross-agent path explicitly** in `concepts.md`: how two agents
   in one workflow share and attribute the same canonical memory.
3. **Surface provenance in user docs** at the right altitude — users need the
   guarantee and how to audit it, not the full manifest-field spec.

## Attribution of the idea

The provenance + thin-context discipline is KB Factory's adaptation of context
engineering (Karpathy) and harness engineering / externalized memory (Carlos
Perez, [@IntuitMachine](https://x.com/IntuitMachine)). See
[ACKNOWLEDGMENTS.md](../ACKNOWLEDGMENTS.md).
