---
name: kb-wiki-maintainer
description: Maintain a project Knowledge Base — ingest raw sources, file typed records, refresh the derived markdown wiki, and run lifecycle maintenance. Use when the project has a `.kb/` directory, when the user mentions "KB", "knowledge base", "ingest source", "session start", "update wiki", "answer from KB", or when bootstrapping memory for a new project.
---

# KB Wiki Maintainer

Use this skill when a project has a `.kb/` directory or when the user wants to ingest sources, update a derived wiki, answer from the KB, or maintain memory lifecycle policies.

## Durable Boundary

- `.kb/` is the durable memory layer.
- Raw sources stay immutable.
- Typed KB records remain canonical.
- The wiki is derived and may be refreshed, linted, or recompiled.
- Plugin, export, and handoff notes stay thin.

## Bootstrapping a new project (no `.kb/` yet)

If the project has no `.kb/` directory, create one before the session flows
below. Two reliable ways:

- **If `kb-factory` is installed** (`pip install kb-factory`): run `kb-factory
  init` in the project root — it scaffolds `.kb/` and initializes the store.
- **Offline / no pip:** this plugin bundles the scaffold under its own
  `scaffold/` directory. Copy that `scaffold/` into the project as `.kb/`, then
  run `python .kb/kb.py init`.

Confirm with `python .kb/kb.py stats`, then continue with Session Start below.

## Session Start

Use the bootstrap mode that matches the session purpose. When in doubt, start thin.

### Thin Bootstrap (default for consumer-project sessions)

1. Run `python .kb/kb.py lifecycle session-start --json`.
2. Read `.kb/memory/NOW.md`.
3. Stop. Load richer context only when the conversation demands it.

### Standard Bootstrap (when the active working set is clearly needed)

1. Run `python .kb/kb.py lifecycle session-start --json`.
2. Read `.kb/memory/NOW.md`.
3. Read `.kb/memory/HOT.md`.
4. Search or check pending as needed based on the conversation topic.

### Deep Review Bootstrap (audit, close-out, or review sessions only)

1. Run `python .kb/kb.py lifecycle session-start --json`.
2. Read `.kb/memory/NOW.md`.
3. Read `.kb/memory/HOT.md`.
4. Read `.kb/memory/INDEX.md`.
5. Load wiki, handoff notes, references, and other materials as needed for the review scope.

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
5. Run `python .kb/kb.py lifecycle source-ingest --json`.
6. If the wiki should be materialized immediately, run `python .kb/kb.py lifecycle source-ingest --sync-wiki --json`.

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

Agents, reviewers, and KB workflows should cite that command's output instead of hardcoding thresholds.

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

### Wiki Activation Modes

The `activation_mode` field in `wiki` config controls how the wiki becomes active:

- **`manual`** (default): Wiki requires `wiki.enabled = true` in config. Current behavior.
- **`signal`**: Wiki activates automatically when hard and soft signal thresholds pass. `enabled = true` acts as an override that bypasses signal checks.
- **`profile`**: Profile presets set eligibility thresholds. Requires `project_profile` to be set. `enabled = true` acts as an override.

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

The operation log tracks lifecycle runs and ingest events as an immutable audit trail. It does not track individual record changes (see `audit_log` for that).

## Session End

If shell access is available:

1. Run `python .kb/kb.py lifecycle session-end --json`.
2. For HOT overflow or semantic hygiene, run read-only `python .kb/kb.py hygiene-audit --json` before any maintenance action.
3. If the project needs a stronger retention pass, run `python .kb/kb.py lifecycle scheduled-maintenance --apply-demotions --json`.

If shell access is not available:

1. Produce a concise maintenance checklist.
2. List the concrete KB writes or wiki updates that should be applied by a shell-capable agent.

## Anti-Patterns

1. Do not create plugin-local durable memory.
2. Do not dump transcripts or raw logs into curated memory.
3. Do not promote too many records to `HOT`.
4. Do not auto-demote HOT records from semantic judgment alone; use proposals or explicit classic KB commands.
5. Do not treat the wiki as the canonical truth when the KB says otherwise.
6. Do not let session and handoff notes become a shadow KB.

See `reference.md` for lifecycle and automation guidance.

---

[^1]: As of WP-KBF.18, `session-start --json` emits a `filing_suggestions` list alongside existing keys. Each suggestion is advisory only (`enforcement_mode: "advisory"`) and carries `type`, `reason`, `confidence_band`, and `recommended_action`. No gating occurs; treat suggestions as prompts to review, not requirements to act.
