---
description: Upgrade KB/Wiki vNext in an existing project without changing canonical KB.
allowed-tools: Read, Write, Edit, Bash, Grep, Glob
---

Upgrade KB/Wiki vNext in an existing project.

Use this when replacing an installed vNext package or runtime while preserving
classic `.kb/` as canonical memory.

1. Record the current plugin and `.kb-next/runtime/kb_next.py` versions. Keep the
   previous ZIP available for rollback.
2. Install the new platform artifact for Codex, Claude Code, or Claude Cowork.
3. Resolve the NEW source runtime without using the existing workspace runtime:
   - `${CLAUDE_PLUGIN_ROOT}/runtime/kb_next.py` for the newly installed plugin;
   - otherwise the newly installed client plugin directory matching
     `**/kb-wiki-vnext/runtime/kb_next.py`;
   - in the KB Factory authoring monorepo only,
     `core/versions/kb-wiki-vnext/runtime/kb_next.py`.
4. If no new source runtime resolves, stop and report a broken/incomplete new
   artifact. Do not claim upgrade success and do not hand-place a runtime.
5. Update only the workspace vNext runtime:
   `python <new-source-runtime> --project-root . bootstrap --json`
   Require an `action` of `created`, `updated`, or `exists` with the expected
   new runtime version, and require `source_sha256` to equal
   `installed_sha256`. An `action` of `self` is not upgrade proof.
6. Refresh the classic engine without touching data or config:
   `python .kb-next/runtime/kb_next.py upgrade-classic --json`
   It copies only `kb.py` and `runtime/*.py` from the installed kb-lifecycle
   scaffold (never `kb.db`, `memory/`, `sources/`, `wiki/` or
   `kb.config.json`). If no classic template resolves, report it and continue
   with the vNext upgrade only.
7. Re-apply the recorded activation mode so the classic config is aligned
   (read `sponsor_decision` from `.kb-next/decisions/activation-decision.json`):
   `python .kb-next/runtime/kb_next.py activation-wizard --mode short --choice kb-wiki --json`
   (use `--choice kb-alone` when that is the recorded decision)
   The wizard merges and keeps operator edits; for `kb-wiki` it enables the
   classic wiki and its lifecycle sync (the fix for projects activated before
   0.1.10) and records `classic-config-sync` in `.kb-next/operations.jsonl`.
8. Normalize legacy absolute source paths once:
   `python .kb/kb.py source-relink --json` (use `--dry-run` first to preview).
9. Do not overwrite `.kb/` data. Run `existing-project-verify-install` using the
   refreshed `.kb-next/runtime/kb_next.py`.
10. Report old/new versions, ZIP name, bootstrap action, classic engine files
    changed, classic config sync, and verification result.
