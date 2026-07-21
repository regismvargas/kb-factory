# KB/Wiki vNext Command Reference

Use explicit command names. Do not use generic `/session-start` or
`/session-end` aliases for vNext or Session Gate packages.

Runtime paths are resolved separately from plugin command names. For normal
shell sessions use `./.kb-next/runtime/kb_next.py`; if absent, resolve the
plugin-bundled `runtime/kb_next.py` and run `bootstrap`. Use the authoring
`core/versions/...` path only inside KB Factory.

The table below uses **logical basenames**, not one literal invocation for all
clients:

| Client | Startup invocation |
|---|---|
| Claude Code | `/kb-wiki-vnext:vnext-session-start` |
| Codex | invoke the embedded `kb-wiki-vnext` skill in natural language; use the runtime fallback when needed |
| Claude Cowork | use the namespaced action exposed by the installed plugin UI, or invoke the skill in natural language; use the runtime fallback when commands are not exposed |

Do not promise a bare slash command such as `/vnext-session-start` across
clients. Session Gate follows the same distinction with the logical basename
`gate-session-start`.

| Command | Project type | Platforms | Runtime or instruction | Mutation behavior |
|---|---|---|---|---|
| `vnext-session-start` | general vNext session | Codex, Claude Code, Claude Cowork | `python ./.kb-next/runtime/kb_next.py session-start --json` after bootstrap | no canonical write; appends `.kb-next/operations.jsonl` |
| `vnext-session-end` | general vNext session | Codex, Claude Code, Claude Cowork | summarize vNext evidence | no canonical write by default |
| `existing-project-diagnose` | existing/legacy | Codex, Claude Code, Claude Cowork | inspect `.kb/`, `.kb-next/`, runtime, and `NOW.md` | no canonical write; appends operations evidence if it runs `session-start` |
| `existing-project-activate-vnext` | existing/legacy | Codex, Claude Code, Claude Cowork | `activation-wizard --mode short --choice kb-alone` by default | writes `.kb-next/`, not `.kb/` |
| `existing-project-configure-vnext` | existing/legacy | Codex, Claude Code, Claude Cowork | short or guided `activation-wizard` | writes `.kb-next/`, not `.kb/` |
| `existing-project-verify-install` | existing/legacy | Codex, Claude Code, Claude Cowork | `session-start` plus deterministic `lookup` | no canonical write; appends `.kb-next/operations.jsonl` |
| `existing-project-upgrade-vnext` | existing/legacy | Codex, Claude Code, Claude Cowork | bootstrap from replacement artifact and verify expected version | package/workspace runtime plus operational evidence; no canonical write |
| `existing-project-rollback-vnext` | existing/legacy | Codex, Claude Code, Claude Cowork | bootstrap from restored artifact and verify prior version | package/workspace runtime plus operational evidence; no canonical write |
| `new-project-wizard` | new project | Codex, Claude Code, Claude Cowork | seed classic template if needed and choose init mode | creates `.kb/` and `.kb-next/` when absent |
| `new-project-init-kb-alone` | new project | Codex, Claude Code, Claude Cowork | `activation-wizard --mode short --choice kb-alone` | creates/configures `.kb-next/` |
| `new-project-init-kb-wiki` | new project | Codex, Claude Code, Claude Cowork | `activation-wizard --mode short --choice kb-wiki` | creates/configures `.kb-next/`; no live publish |
| `new-project-verify-install` | new project | Codex, Claude Code, Claude Cowork | `session-start` plus deterministic `lookup` | no canonical write; appends `.kb-next/operations.jsonl` |
| `gate-session-start` | Session Gate | Codex, Claude Code, Claude Cowork | detect `.kb-next/`, `.kb/`, CASE; route vNext first | no canonical write; vNext route appends `.kb-next/operations.jsonl` |
| `gate-session-end` | Session Gate | Codex, Claude Code, Claude Cowork | detect systems and summarize closeout | no canonical write by default |

Runtime-only command:

| Subcommand | Purpose | Mutation behavior |
|---|---|---|
| `bootstrap` | atomically install the executing artifact runtime at `<project>/.kb-next/runtime/kb_next.py` | replaces byte drift, reports source/installed SHA-256, rejects unsafe targets; `action: self` is not upgrade proof |

Classic `.kb/` remains canonical durable memory. `.kb-next/` remains governed
proposal, evidence, draft, materialization, and operations state.

## Graph surfaces

The vNext runtime exposes pure reads. Every command opens `.kb/kb.db` with
SQLite URI `mode=ro` and `PRAGMA query_only=ON`:

| Command | Result | Exit codes |
|---|---|---|
| `graph backlinks RECORD_ID [--json]` | pages stored in `wiki_page_provenance` | `0`, or `2` for usage/environment error |
| `graph lineage RECORD_ID [--json]` | roots, current tips, branches, cycles, and encoding divergence | `0`, or `2` |
| `graph neighbors RECORD_ID [--json]` | de-duplicated neighbors with separate `origins[]` | `0`, or `2` |
| `graph source-records SOURCE_ID [--json]` | both source-link encodings and any divergence | `0`, or `2` |
| `graph verify [--json]` | deterministic findings with stable issue codes | `0` clean, `1` findings, `2` error |
| `graph source-backfill [--limit 1..3] [--json]` | bounded exact-evidence proposals; never applies them | `0`, or `2` |

All JSON responses use `graph_contract_version`, `command`, `subject`,
`results`, `warnings`, and `blind_spots`. Schema v5 remains readable; missing
typed edges produce `TYPED_EDGE_CAPABILITY_UNAVAILABLE`.

Canonical graph mutations exist only in the classic runtime:

```text
graph edge-add SOURCE_RECORD TYPE TARGET_RECORD --actor ID --actor-runtime human|codex|claude-code|cowork [--note TEXT]
graph edge-remove EDGE_ID --actor ID --actor-runtime human|codex|claude-code|cowork [--note TEXT]
graph source-link RECORD_ID SOURCE_ID --actor ID --actor-runtime human|codex|claude-code|cowork [--note TEXT]
```

Allowed edge types are `depends-on`, `contradicts`, and `duplicates`.
Mutations, audit rows, and operations rows commit in one transaction.
