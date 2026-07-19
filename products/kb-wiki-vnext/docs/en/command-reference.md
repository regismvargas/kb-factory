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
