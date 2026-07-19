# KB Wiki Maintainer Reference

This reference expands the shared operating model behind the `kb-wiki-maintainer` skill.

## Memory Lifecycle

The package assumes five practical layers:

1. raw sources
2. working observations
3. episodic digests
4. semantic records
5. procedural memory

KB Factory v1.5 already supports parts of this model through typed records, tiers, review dates, and consolidation. The distributed skill should preserve those semantics instead of bypassing them.

## Confidence, Supersession, And Forgetting

- Confidence is a routing and review signal, not a license to mutate history casually.
- Supersession is the correct operation when a claim changes meaning.
- Forgetting means reducing retrieval priority or moving material out of the default working set, not silent deletion.

## Automation Pattern

The target workflow is event-driven:

- on new source: summarize, update records, run `lifecycle source-ingest`
- on session start: run `python .kb/kb.py lifecycle session-start --json`, then load `NOW` (load `HOT` only if the session needs the active working set)
- on session end: run `python .kb/kb.py lifecycle session-end --json`
- on query: decide whether the result should be filed back
- on schedule: run `lifecycle scheduled-maintenance`

The current distributed package ships only a lightweight session-start hook for Claude environments. Scheduled maintenance should be implemented through Codex automations or Claude scheduled prompts until the runtime grows stronger native lifecycle hooks.

## Shell And No-Shell Modes

When shell access exists:

- operate the local `.kb/kb.py`
- write durable changes directly
- refresh exports and the wiki

When shell access does not exist:

- operate on exported `NOW`, `HOT`, `INDEX`, and project packs
- produce explicit proposed writes
- file durable results through a shell-capable agent or follow-up task

## CASE Boundary

CASE projects already use the clone-kit `.kb/` scaffold. This skill must stay compatible with that contract:

- no second durable memory store
- no plugin-owned replacement for `NOW`, `HOT`, or `INDEX`
- no local override of canonical record types or tiers
