---
description: Close a KB/Wiki vNext session with governed operational evidence.
allowed-tools: Read, Write, Edit, Bash, Grep, Glob
---

Close a KB/Wiki vNext session by recording only useful operational evidence.

Use this explicit command instead of a generic `/session-end` alias so vNext,
Session Gate, and classic KB lifecycle commands cannot collide.

1. Summarize vNext manifests, proposals, package checks, tests, or pilot
   evidence touched in the session.
2. Do not write durable memory unless the user approved canonical KB changes.
3. If a canonical KB update is approved, use `.kb/kb.py` or an already approved
   `proposal-apply` flow. `proposal-apply` needs `--actor` set to the person
   who approved (ask if unknown; omit it only when that person is the
   `proposal_apply.default_actor` of the vNext config) and `--actor-runtime`
   set to this runtime.
4. If `.kb/kb.py` exists, run `python .kb/kb.py lifecycle session-end --json`.
   It refreshes exports and, when the classic wiki is enabled, syncs
   `.kb/wiki/live`. Report `wiki_sync.written_count` and any `held_back`
   pages.
5. If KB + Wiki is active, resolve the vNext runtime (`.kb-next/runtime/kb_next.py`,
   then `${CLAUDE_PLUGIN_ROOT}/runtime/kb_next.py`) and run
   `python <resolved-runtime-path> wiki-draft-status --json`. When any topic
   is `needs_synthesis`, `needs_review` or `stale`, offer to run the
   `vnext-wiki-drafts` command now or list the topics for the next session.
6. If `retrieval.dense.enabled` is `true` in `.kb-next/kb-next.config.json`
   and records were filed or edited in the session, refresh the dense index
   with `python <resolved-runtime-path> dense-index --json` (it embeds only
   new or changed records). If it fails for a missing extra or model, report
   the message; lookup still ranks by words.
