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
| `vnext-session-end` | general vNext session | Codex, Claude Code, Claude Cowork | summarize vNext evidence; run `python .kb/kb.py lifecycle session-end` and, with KB + Wiki, the runtime `wiki-draft-status` | classic session-end refreshes exports and the enabled wiki; no canonical record write |
| `vnext-wiki-drafts` | KB + Wiki session | Codex, Claude Code, Claude Cowork | `wiki-draft-status`, then per topic `wiki-synthesis-plan` with agent judgment and `wiki-draft-review --materialize` | writes `.kb-next/wiki/` drafts, manifests and pages; no canonical write |
| `existing-project-diagnose` | existing/legacy | Codex, Claude Code, Claude Cowork | inspect `.kb/`, `.kb-next/`, runtime, and `NOW.md` | no canonical write; appends operations evidence if it runs `session-start` |
| `existing-project-activate-vnext` | existing/legacy | Codex, Claude Code, Claude Cowork | `activation-wizard --mode short --choice kb-alone` by default | writes `.kb-next/`; with `kb-wiki` also enables the classic wiki keys in `.kb/kb.config.json` and syncs `.kb/wiki/live` |
| `existing-project-configure-vnext` | existing/legacy | Codex, Claude Code, Claude Cowork | short or guided `activation-wizard` (merges the existing config) | writes `.kb-next/`; `kb-wiki` enables and syncs the classic wiki; `kb-alone` keeps it unless `--disable-classic-wiki` |
| `existing-project-verify-install` | existing/legacy | Codex, Claude Code, Claude Cowork | `session-start` plus deterministic `lookup` | no canonical write; appends `.kb-next/operations.jsonl` |
| `existing-project-upgrade-vnext` | existing/legacy | Codex, Claude Code, Claude Cowork | bootstrap from replacement artifact, `upgrade-classic`, re-apply the recorded mode, verify | workspace runtimes, classic engine files and classic wiki keys; no canonical record write |
| `existing-project-rollback-vnext` | existing/legacy | Codex, Claude Code, Claude Cowork | bootstrap from restored artifact and verify prior version | package/workspace runtime plus operational evidence; no canonical write |
| `new-project-wizard` | new project | Codex, Claude Code, Claude Cowork | ask for title, slug and domains, then choose the init mode | creates `.kb/` (through `install-classic`) and `.kb-next/` when absent |
| `new-project-init-kb-alone` | new project | Codex, Claude Code, Claude Cowork | `install-classic`, `bootstrap`, `activation-wizard --mode short --choice kb-alone` | creates `.kb/` when absent and configures `.kb-next/` |
| `new-project-init-kb-wiki` | new project | Codex, Claude Code, Claude Cowork | `install-classic`, `bootstrap`, `activation-wizard --mode short --choice kb-wiki` | creates `.kb/` when absent and `.kb-next/`; enables the classic wiki and publishes `.kb/wiki/live`; vNext drafts are never copied there |
| `new-project-verify-install` | new project | Codex, Claude Code, Claude Cowork | `session-start` plus deterministic `lookup` | no canonical write; appends `.kb-next/operations.jsonl` |
| `gate-session-start` | Session Gate | Codex, Claude Code, Claude Cowork | detect `.kb-next/` and `.kb/`; route vNext first | no canonical write; vNext route appends `.kb-next/operations.jsonl` |
| `gate-session-end` | Session Gate | Codex, Claude Code, Claude Cowork | detect systems and summarize closeout | no canonical write by default |

Runtime-only commands:

| Subcommand | Purpose | Mutation behavior |
|---|---|---|
| `bootstrap` | atomically install the executing artifact runtime at `<project>/.kb-next/runtime/kb_next.py` | replaces byte drift, reports source/installed SHA-256, rejects unsafe targets; `action: self` is not upgrade proof |
| `install-classic` | copy the classic scaffold (kb-lifecycle plugin, stand-alone bundle, authoring repo or `--template`) into `.kb/` and run classic `init --name --slug --domains` | creates `.kb/`; refuses an existing or non-empty `.kb/` |
| `upgrade-classic` | refresh only `.kb/kb.py` and `.kb/runtime/*.py` from the discovered scaffold | engine files only; never `kb.db`, data or `kb.config.json` |
| `wiki-draft-status` | list wiki topics that need synthesis, review or refresh | read-only |
| `session-hint` | SessionStart hook text for vNext workspaces | read-only; prints nothing outside vNext workspaces |

Classic `.kb/` remains canonical durable memory. `.kb-next/` remains governed
proposal, evidence, draft, materialization, and operations state.
