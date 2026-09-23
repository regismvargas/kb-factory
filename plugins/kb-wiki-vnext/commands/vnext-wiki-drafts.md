---
description: Draft, review and materialize KB + Wiki vNext pages for pending topics.
allowed-tools: Read, Write, Edit, Bash, Grep, Glob
---

Draft, review and materialize vNext wiki pages for topics that need them.

Use this when KB + Wiki is active and the runtime `session-start` JSON or the
`vnext-session-end` plugin command reports pending wiki drafts. The judgment step needs you (the agent): the
runtime supplies candidate records and validates what you return; it never
invents page content.

1. Resolve the vNext runtime. Check these paths in order and use the first
   that exists:
   - `.kb-next/runtime/kb_next.py` (runtime installed in the workspace)
   - `${CLAUDE_PLUGIN_ROOT}/runtime/kb_next.py` (engine bundled in this plugin;
     Claude Code sets `CLAUDE_PLUGIN_ROOT`)
   - `core/versions/kb-wiki-vnext/runtime/kb_next.py` (KB Factory authoring
     monorepo only)
   If none resolves, report that the vNext runtime is not installed and stop.
2. List the backlog:
   `python <resolved-runtime-path> wiki-draft-status --json`
   Each topic has a `state` (`needs_synthesis`, `needs_review`, `stale`,
   `current`) and the exact `next_args` to run. Stop if `wiki_enabled` is
   false and suggest `existing-project-configure-vnext` with `kb-wiki`.
3. For each `needs_synthesis` or `stale` topic, in the order listed:
   a. `python <resolved-runtime-path> wiki-synthesis-plan --topic "<topic>" --domain "<domain>" --json`
      returns `candidate_records` and an `llm_task`.
   b. Write a judgment JSON file outside the repository (for example in the
      system temp directory) with
      `supporting_record_ids` (only IDs from `candidate_records`), `rationale`,
      `confidence` (0 to 1, honest), `machine_draft` and `human_draft`
      (Markdown bodies grounded only in those records). Do not add facts that
      the records do not state.
   c. `python <resolved-runtime-path> wiki-synthesis-plan --topic "<topic>" --domain "<domain>" --judgment @<file> --write-drafts --json`
4. For each topic with drafts (`needs_review`, or after step 3):
   `python <resolved-runtime-path> wiki-draft-review --topic "<topic>" --materialize --json`
   `status: valid` with `materialized: true` means the pages were written to
   `.kb-next/wiki/{machine,human}`. Any other status lists the warnings to fix;
   do not force publication.
5. Report per topic: state before, review status, materialized paths, and
   warnings left for the user. Canonical `.kb/` records are never changed by
   this command.
