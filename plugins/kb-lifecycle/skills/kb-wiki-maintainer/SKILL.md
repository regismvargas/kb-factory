---
name: kb-wiki-maintainer
description: Maintain a project Knowledge Base, ingest raw sources, file typed records, refresh the derived markdown wiki, and run lifecycle maintenance. Use when the project has a `.kb/` directory, when the user mentions "KB", "knowledge base", "ingest source", "session start", "update wiki", "answer from KB", or when bootstrapping memory for a new project.
---

# KB Wiki Maintainer

Use this skill when a project has a `.kb/` directory or when the user wants to ingest sources, update a derived wiki, answer from the KB, or maintain memory lifecycle policies.

## Durable Boundary

- `.kb/` is the durable memory layer.
- Raw sources stay immutable.
- Typed KB records remain canonical.
- The wiki is derived and may be refreshed, linted, or recompiled.
- Plugin, export, and dispatch artifacts stay thin.

## Bootstrapping A New Project

If the project has no `.kb/` directory, establish the canonical runtime before
using the session flows below:

- If the public Python package is installed, run `kb-factory init` in the
  project root.
- Otherwise copy this plugin's bundled `scaffold/` directory to `.kb/`, then
  run `python .kb/kb.py init --name "<Project Title>" --slug <project-slug> --domains <a,b,c> --seed .kb/seed/initial_records.jsonl`.
  The flags render the `{{...}}` placeholders and prefix record IDs with the
  slug (`<SLUG>-KB-...`); ask the user for them instead of inventing them.
  Every platform-specific Lifecycle artifact must carry this scaffold from the
  canonical `core/templates/kb/` source.
- With KB/Wiki vNext installed, `kb_next.py install-classic` performs the same
  copy and init.

Confirm the result with `python .kb/kb.py stats`, and do not create a second
plugin-owned memory store. Every command except `init` refuses to run when
`.kb/kb.db` is missing; it never creates an empty KB silently.

In a linked Git worktree (for example a per-session desktop worktree) the
runtime uses the main worktree's `.kb/` when it has a `kb.db`, so every session
shares one KB. `python .kb/kb.py doctor --json` shows the resolution under
`storage`; set `storage.worktree_scope` to `local` in `kb.config.json` (or
`KB_FACTORY_WORKTREE_SCOPE=local`) only when a worktree needs its own KB.

## Session Start

Use the bootstrap mode that matches the session purpose. When in doubt, start thin.

In a KB/Wiki vNext workspace (`.kb-next/kb-next.config.json` exists), defer to
vNext: use the plugin command `vnext-session-start` (runtime equivalent:
`python .kb-next/runtime/kb_next.py session-start --json`) and read only
`.kb-next/memory/NOW.md` by default. Classic NOW, HOT, and INDEX then become
on-demand reads; the modes below apply to workspaces without vNext.

`python .kb/kb.py lifecycle session-start --json` reports the resolved memory
files under `paths` (`now`, `hot`, `index`). When a linked Git worktree shares
the main worktree's KB (see above), they point at the main worktree's `.kb/`;
read those paths instead of local `.kb/memory/` copies.

### Thin Bootstrap (default for consumer-project sessions)

1. Run `python .kb/kb.py lifecycle session-start --json`.
2. Read `paths.now` from that output (the resolved `NOW.md`).
3. Stop. Load richer context only when the conversation demands it.

### Standard Bootstrap (when the active working set is clearly needed)

1. Run `python .kb/kb.py lifecycle session-start --json`.
2. Read `paths.now` (the resolved `NOW.md`).
3. Read `paths.hot` (the resolved `HOT.md`).
4. Search or check pending as needed based on the conversation topic.

### Deep Review Bootstrap (audit, close-out, dispatch, or review sessions only)

1. Run `python .kb/kb.py lifecycle session-start --json`.
2. Read `paths.now` (the resolved `NOW.md`).
3. Read `paths.hot` (the resolved `HOT.md`).
4. Read `paths.index` (the resolved `INDEX.md`).
5. Load wiki, dispatch packs, references, and other materials as needed for the review scope.

### On-Demand Loading (all modes)

These surfaces are always available during the conversation but are not preloaded at startup:

- `.kb/memory/HOT.md` — load when you need the current working set
- `.kb/memory/INDEX.md` — load when you need the broader KB map
- `python .kb/kb.py search "<term>"` — search before assuming
- `python .kb/kb.py pending` — check open pendencias
- Wiki index and pages — load when wiki context is needed

## Operating Rules

1. Persist only durable and non-derivable knowledge.
2. Use the canonical record types:
   - `DECISAO`
   - `PREMISSA`
   - `FATO`
   - `PENDENCIA`
   - `APRENDIZADO`
3. Use `update` only for routing metadata such as tier, tags, review date, or confidence adjustments.
4. If meaning changed, use `supersede`, not `update`.
5. Forgetting means demotion in retrieval priority, not deleting audit history.
6. If an answer or analysis is worth keeping, file it back into the KB or wiki instead of leaving it in chat history.

## Workflows

### Ingest

1. Register the source file: `python .kb/kb.py ingest <path> --domain <domain> --json`.
   - The file is copied to `.kb/sources/` and cataloged.
   - Duplicate files are skipped automatically by content hash.
2. List registered sources: `python .kb/kb.py sources --json`.
3. Inspect a source: `python .kb/kb.py source-info <source_id> --json`.
4. Read the source and create KB records linked to it:
   - `python .kb/kb.py create --category FATO --domain <domain> --title "..." --content "..." --source-id <source_id> --json`
   - Use `--source-id` on `create` and `supersede` to link records to their originating source.
5. No lifecycle step is needed afterward: `ingest` runs the `source-ingest` lifecycle event and each `create` runs `record-filed`; both refresh exports and, when the wiki is enabled, sync `.kb/wiki/live` (skipped with `--no-auto-lifecycle`). `python .kb/kb.py lifecycle source-ingest --json` remains an optional manual re-run.

### Summarize Sources

1. Check coverage: `python .kb/kb.py summarize-status --json`.
2. For each source where `has_summary` is false:
   a. Read content: `python .kb/kb.py source-content <source_id>`.
   b. Write a structured summary:
      - Overview: 1-2 sentences describing the source.
      - Key points: bullet list of facts and takeaways.
      - Scope: what the source covers and does not.
   c. Assess confidence:
      - 0.8+ → file directly.
      - 0.55-0.8 → present to user for review before filing.
      - below 0.55 → do not file, report to user.
   d. File: `python .kb/kb.py create --category FATO --domain <domain> --title "Summary: <filename>" --content "<structured summary>" --source-id <source_id> --tags source-summary --confidence <value> --json`.
3. To re-summarize a source, supersede the existing summary:
   `python .kb/kb.py supersede <existing_summary_id> --content "<new summary>" --source-id <source_id> --tags source-summary --json`.
4. Verify: `python .kb/kb.py summarize-status --json`.

Do not:
- Dump raw source content as the summary.
- Create multiple active summaries for the same source.
- File summaries with confidence below 0.55 without explicit approval.

### File Analyses

1. Check coverage: `python .kb/kb.py analysis-status --json`.
2. For each source where `has_analysis` is false and a summary exists:
   a. Read source: `python .kb/kb.py source-content <source_id>`.
   b. Review the existing summary.
   c. Write a structured analysis:
      - Thesis: 1-2 sentence core insight.
      - Supporting evidence: bullet list from the source.
      - Implications: strategic takeaways.
      - Limitations: what the analysis does not cover.
   d. Assess confidence (analyses are interpretive — default slightly lower than summaries):
      - 0.8+ → file directly.
      - 0.55-0.8 → present to user for review.
      - below 0.55 → do not file without approval.
   e. File: `python .kb/kb.py create --category APRENDIZADO --domain <domain> --title "Analysis: <filename>" --content "<structured analysis>" --source-id <source_id> --tags filed-analysis --confidence <value> --json`.
3. To update an analysis, supersede:
   `python .kb/kb.py supersede <existing_analysis_id> --content "<new analysis>" --source-id <source_id> --tags filed-analysis --json`.
4. Verify: `python .kb/kb.py analysis-status --json`.

Do not:
- Restate facts already in the summary (reference the summary instead).
- Create multiple active analyses for the same source.
- File analyses for sources that haven't been summarized first.
- Attempt multi-source analysis (single-source only in current version).

Note: For source-linked analyses, you can also use `python .kb/kb.py file --filing-type analysis` which automatically tags and logs the filing to the operation log.

### File Durable Answers

Use the `file` command when a conversation result has lasting value and should be preserved as a KB record. This command wraps `create` with explicit filing intent, automatic tagging, and operation log auditing.

**Filing policy is advisory.** The runtime does not gate `kb file` on category, confidence, or provenance. Enforcement is agent + operator responsibility. The authoritative thresholds and per-type expectations are defined by the project policy — read them with:

```
python .kb/kb.py filing-policy --json
```

Agents, reviewers, and workflows should cite that command's output instead of hardcoding thresholds.

#### When to File

Source: `filing_policy.when_to_file`. Typical criteria:

- The answer captures a durable insight, decision rationale, or synthesis reusable across sessions.
- The result distills knowledge from multiple records, sources, or conversation threads.
- Losing this answer to chat history would be a meaningful loss.

#### When NOT to File

Source: `filing_policy.when_not_to_file`. Typical criteria:

- The answer is transient (e.g., a formatting question, a one-off lookup).
- The content is already covered by an existing active KB record — supersede that record instead.
- Confidence is below the review band without explicit operator approval.

#### Filing Types

- **answer**: A standalone durable answer not tied to a specific source. Use when the insight comes from reasoning, cross-referencing, or conversation synthesis.
- **analysis**: A source-linked interpretive analysis. Use with `--source-id`. Equivalent to the existing analysis filing workflow.
- **synthesis**: A cross-source or cross-record integration. Use when the value comes from combining multiple inputs into a unified view.

The filing type determines the automatic tag (`filed-answer`, `filed-analysis`, `filed-synthesis`). It does NOT determine the record category — choose `FATO`, `APRENDIZADO`, `DECISAO`, or `PREMISSA` based on the nature of the content. Per-type `allowed_categories` and `requires_source_id` expectations are listed in the policy readout.

#### Confidence Bands

Bands come from `filing_policy.confidence_bands`. Read them with `python .kb/kb.py filing-policy --json`. Behavioral guidance at each band:

- confidence ≥ `high` → file directly.
- `review` ≤ confidence < `high` → present to user for review before filing.
- confidence < `review` → do not file without explicit approval.

Do not hardcode the numeric values in skill or workflow guidance. The policy is the single source of truth; changing a threshold means editing `kb.config.json#filing_policy` and the new value flows to `filing-status` banding and to every consumer of `filing-policy --json`.

#### Commands

File an answer:
```
python .kb/kb.py file --filing-type answer --category APRENDIZADO --domain <domain> --title "..." --content "..." --confidence <value> --json
```

File a source-linked analysis:
```
python .kb/kb.py file --filing-type analysis --category APRENDIZADO --domain <domain> --title "Analysis: <filename>" --content "..." --source-id <source_id> --confidence <value> --json
```

File a synthesis:
```
python .kb/kb.py file --filing-type synthesis --category FATO --domain <domain> --title "..." --content "..." --confidence <value> --json
```

Check filing status: `python .kb/kb.py filing-status --json`
Check filing audit trail: `python .kb/kb.py oplog --category record_filing --json`

#### Do Not

- File every answer — only file what has lasting value.
- Skip choosing a category — the filing type is about provenance intent, not content nature.
- Create duplicate filings for the same insight.
- Use `file` as a replacement for `create` when there is no filing intent.

### Query

1. Search the KB and the wiki index first.
2. Answer with citations or explicit provenance.
3. Decide whether the result should become a durable analysis page or KB record.

### Lint

Look for:

- contradictions
- stale premises
- orphan or thin wiki pages
- concepts mentioned but not represented
- analyses worth filing back

### Wiki Page Structure

Domain overview pages are grouped by record category in this order:
- **Key Decisions** (DECISAO)
- **Facts & Evidence** (FATO)
- **Learnings** (APRENDIZADO)
- **Open Questions** (PENDENCIA)
- **Premises** (PREMISSA)

Each record shows its tier badge (`[HOT]`, `[WARM]`, `[COLD]`), title, and a content excerpt (up to ~200 characters). Records within each group are ordered by tier (HOT first) then recency.

If the domain contains source-linked summaries (FATO + `source-summary` tag) or filed analyses (APRENDIZADO + `filed-analysis` tag), a "Sources & Analyses" section appears at the bottom. Categories with no records are omitted.

Research synthesis pages use the same category-grouped format as domain overviews, without the Sources & Analyses section (since they aggregate across domains by tag).

Source detail pages are generated for sources that have linked records, a summary, or a filed analysis. Each source page shows source metadata, the summary (if present), the analysis (if present), and linked records. Sources with no linked data do not generate pages.

Other page types use a flat bullet-list format.

All wiki pages remain deterministic and rebuildable from DB state.

### Turning The Wiki On

Run `python .kb/kb.py wiki-config --enable --json` once. It sets
`wiki.enabled = true`, enables `run_wiki_sync` on the `record_filed`,
`source_ingest`, `session_end` and `scheduled_maintenance` lifecycle events
(keeping every other config key), and runs the first `wiki-sync`. From then
on `create`, `file`, `supersede`, `resolve`, `ingest` and
`lifecycle session-end` keep `.kb/wiki/live` current with no manual sync.
`wiki-config --disable` turns it off. `wiki-check --json` reports the state,
`lifecycle_sync_events`, and under `publication` which candidates would
publish and which are held back by a hygiene gate (with the reason).

### Wiki Activation Modes

The `activation_mode` field in `wiki` config controls how the wiki becomes
active when it is not explicitly enabled:

- `wiki.enabled = true` always turns the wiki on, in every mode; signals never veto an explicit opt-in.
- **`manual`** (default): with `enabled = false` the wiki stays off.
- **`signal`**: with `enabled = false` the wiki activates when the hard and soft signal thresholds pass.
- **`profile`**: like `signal`, with thresholds from `project_profile` presets.

Available profiles (set via `wiki.project_profile`):

| Profile | `min_active_records` | `min_soft_signal_score` | Wiki stance |
|---------|---------------------|------------------------|-------------|
| `corporate_companion` | 50 | 2 | Selective |
| `strategic_framework` | 15 | 1 | Required |
| `hybrid_research_ops` | 30 | 1 | Recommended |

User-specified eligibility thresholds in config always override profile presets. Use `wiki-check --json` to inspect the effective thresholds and activation decision.

## Operation Log

Review recent operational events: `python .kb/kb.py oplog --json`.
Filter by category: `python .kb/kb.py oplog --category lifecycle --json`.

The operation log tracks lifecycle runs and ingest events as an immutable audit trail. It does not track individual record changes (see `audit_log` for that). A read-only `python .kb/kb.py lifecycle session-start` writes no row, and read commands (`list`, `get`, `search`, `stats`, `pending`, `wiki-check`, `doctor`) open the database read-only, so reading never changes `kb.db`. Record access counting is opt-in (`tracking.record_access`).

## Source Paths

New sources are stored with KB-relative paths, so the KB survives a move or a
fresh clone. For KBs created before 0.2.4, run
`python .kb/kb.py source-relink --dry-run --json` and then without
`--dry-run` to rewrite legacy absolute paths.

## Session End

If shell access is available:

1. Run `python .kb/kb.py lifecycle session-end --json`. When the wiki is
   enabled this also syncs `.kb/wiki/live`.
2. For HOT overflow or semantic hygiene, run read-only
   `python .kb/kb.py hygiene-audit --json` before any maintenance action.
3. If the project needs a stronger retention pass, run
   `python .kb/kb.py lifecycle scheduled-maintenance --apply-demotions --json`.

If shell access is not available:

1. Produce a concise maintenance checklist.
2. List the concrete KB writes or wiki updates that should be applied by a shell-capable agent.

## Anti-Patterns

1. Do not create plugin-local durable memory.
2. Do not dump transcripts or raw logs into curated memory.
3. Do not promote too many records to `HOT`.
4. Do not auto-demote HOT records from semantic judgment alone; use governed
   proposals or explicit classic KB commands.
5. Do not treat the wiki as the canonical truth when the KB says otherwise.
6. Do not let workflow artifacts become a shadow KB.

See `reference.md` for lifecycle and automation guidance.

---

[^1]: As of WP-KBF.18, `session-start --json` emits a `filing_suggestions` list alongside existing keys. Each suggestion is advisory only (`enforcement_mode: "advisory"`) and carries `type`, `reason`, `confidence_band`, and `recommended_action`. No gating occurs; treat suggestions as prompts to review, not requirements to act.
