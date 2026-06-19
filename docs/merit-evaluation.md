# KB Factory — Merit Evaluation (adversarial · hostile · moderated)

> **What this is.** Before publishing KB Factory, we ran a structured multi-agent
> debate to stress-test whether it has *real* merit and *real* utility as an
> open-source project — not to flatter it. Three independent agents — an
> **Adversarial** steelman critic, a **Hostile** bad-faith critic, and an
> **Advocate** — read the actual code and docs, then debated across two rebuttal
> rounds. A **moderator** (senior LLM-agents / memory-systems profile) rendered
> the verdict. Every claim below was checked against the code locations cited
> inline. The full transcript is in the appendix.
>
> We publish this because the honest answer ("narrow but real, with conditions")
> is more useful to you than a sales pitch — and because the
> [comparison](comparison.md) page leans on it.

## Bottom line

- **Verdict:** MERIT = **moderate (narrow)**. One genuinely defensible idea (a
  non-destructive, provenance-anchored decision ledger) surrounded by ceremony
  and redundancy.
- **Confidence:** **HIGH** — all three sides converged on the same surviving
  asset *and* the same fatal liability.
- **Recommendation:** **GO-WITH-CONDITIONS** for OSS publication (3 hard
  conditions below — all treated as release blockers and addressed before
  shipping; see [What changed in response](#what-changed-in-response)).
- **The one liability that dominated at evaluation time:** the strongest argument
  *for* the project (cross-runtime continuity) and the strongest argument
  *against* it (derived-surface drift) are the **same mechanism**, and in the
  authoring repo the negative dominated (40 wiki-lint issues, 14 stale pages, 2
  source hash mismatches, live/template runtime drift). That drift was fixed
  before release.

---

## Moderator verdict (verbatim)

### 1. Verdict
**MERIT: moderate (narrow).** KB Factory contains one genuinely defensible
architectural idea — a non-destructive, provenance-anchored decision ledger —
surrounded by a large amount of ceremony, redundancy, and (at evaluation time)
self-inflicted unreliability. The merit is real but it is *one mechanism, not a
product*. Strip the supersession invariant and the FK-validated provenance chain,
and what remains is reproducible by `CLAUDE.md` + git + the in-box
consolidate/auto-memory stack at lower cost.

**UTILITY: for a specific, narrow user:**
- **Who:** a single developer (or very small team) who lives in Claude Code,
  distrusts/cannot use cloud memory, and has a project where *a wrong premise
  compounds over time* — where "when did this stop being true and what
  overturned it?" is a high-value, frequently-asked question.
- **Wins:** offline/air-gapped work; audit/compliance-adjacent projects needing
  a git-reviewable, append-only belief history with source-to-record provenance;
  long-lived projects (months+) where reconstructing the *history* of a decision
  matters more than recalling the *current* state.
- **Loses:** solo/short projects (overhead dominates), paraphrased/relational
  recall (keyword FTS loses to any embedding/graph system), multi-agent
  concurrent writes, and any user unwilling to sustain filing discipline. For the
  median Claude Code user, `CLAUDE.md` + auto-memory is the correct choice.

### 2. Confidence
**HIGH.** The decisive facts are mechanical and were independently verified by
all three debaters against the same code locations, with no factual dispute
remaining at the crux. Prosecution and defense agreed on both the asset
(non-destructive supersession) and the liability (derived-surface drift). Only
residual uncertainty is forward-looking (whether hygiene debt is fixable with
automation — plausible, and since addressed in-repo).

### 3. Decisive points
1. **"git already does non-destructive history" (Hostile) vs. "the in-box stack
   is lossy by design" (Advocate).** *Advocate wins on partial merit; Hostile
   lands a real dent.* The surviving claim narrows from "auditable history" to
   **structured/queryable, source-linked, supersession-graphed** history
   (`supersedes_id` + `source_id` FK) — which `git blame` over prose does not
   give. Real but thin delta.
2. **Derived-surface drift (all sides).** *Adversarial/Hostile win decisively.*
   In the authoring repo the discipline produced 40 lint issues, 14 stale pages,
   2 hash mismatches, and live/template drift. "The differentiator and the defect
   are the same mechanism."
3. **"Consolidate is oversold."** *Adversarial wins by concession.* `consolidate`
   is `GROUP BY lower(title)` + date demotion (`maintenance.py:54, 234`) —
   mechanical, not semantic.
4. **Supersession-vs-consolidate inversion.** *Advocate wins on the asset's
   existence.* `update` refuses meaning-mutation (`records.py:230`); `supersede`
   writes a linked new row and marks the old `SUPERSEDIDO` (`records.py:247-285`).
   The honest core; even the prosecution granted it.
5. **"Token-budgeted hard contract."** *Adversarial wins.* Caps (HOT=12, NOW=3+3)
   bound the *export*, not the session. A nicety, not a differentiator.

### 4. Honest positioning (survives the hostile critique)
> **"Where Anthropic's memory stack is consolidative by design — it improves the
> current snapshot by overwriting the past — KB Factory is append-only by design:
> every superseded decision stays as a linked, source-attributed row, so you can
> mechanically reconstruct what the project believed at any past point and exactly
> what overturned it."**

Do **not** market "cross-runtime continuity," "intelligent consolidation," or
"minimal context contract" as differentiators — each was dismantled.

### 5. Findings, triaged

**KEEP (foreground — the real, surviving merit):**
- The **non-destructive supersession invariant**. Lead with it.
- The **provenance chain**: `source_id` FK validation + `source-verify` hash-drift
  detection. A trust property no file-CRUD memory enforces.
- **Stdlib-only / offline / single-file SQLite.** Frame as "auditable in an
  afternoon, runs on a plane, one-file backup" — not as an epistemic claim.
- The **detector working**: `doctor`/`wiki-lint` *can* mechanically flag
  staleness — a differentiator, but only once gated (see FIX).

**FIX (had to be addressed before publishing — these would otherwise falsify the
pitch):**
- **Derived-surface drift is fatal to a trust product.** Gate releases on
  `doctor`/`wiki-lint`/the template-parity test in CI + pre-commit. Ship the
  authoring repo **clean** (0 lint, 0 stale, 0 hash drift). "A trust system whose
  own instance lies is dead on arrival."
- **Documentation honesty on `consolidate`.** State plainly: mechanical dedupe +
  date-based tier demotion; semantic merge is the operator's/LLM's job.
- **Decouple the differentiator from the drift surface.** Either regenerate the
  derived surfaces atomically with a freshness stamp + staleness guard, or stop
  calling them a "synchronized cross-runtime store" and call them point-in-time
  exports.

**CUT (or hide — ceremony that raises evaluation cost):**
- The **"cross-runtime continuity moat"** claim (collapsed in debate).
- The **triplicated runtime** (`core/runtime`, `core/templates/kb/runtime`,
  `.kb/runtime`) — collapse to one source-of-truth + a generation step.
- **Surface-area / jargon overhead**: a large CLI surface, bilingual docs, and a
  framework-specific governance vocabulary. For OSS: an English-first quickstart
  using ~5 commands (`init`, `file`, `search`, `supersede`, `session-start`);
  hide governance vocabulary in an advanced doc.
- **"Token-budgeted hard contract"** as a selling point (keep the caps, drop the
  "contract" framing).

### 6. Recommendation
**GO-WITH-CONDITIONS.** The project has one genuine, defensible idea and a
coherent (if narrow) niche that no named alternative serves cleanly at once —
enough to *exist* as an honest OSS project. At evaluation time it did **not** yet
clear the bar for *a trust product*, because its own repo violated its central
promise. The conditions below were the price of clearing that bar.

**Top 3 conditions (all required before release):**
1. **Ship clean and gate it.** The authoring `.kb/` must pass
   `doctor`/`wiki-lint`/template-parity with zero findings, enforced in CI +
   pre-commit. The detector must be enforcement, not diagnosis.
2. **Rewrite the pitch to the surviving truth.** Headline = the append-only,
   source-attributed, queryable decision ledger (§4). Explicitly disclaim
   semantic consolidation, cross-runtime sync, and recall-quality parity with
   Mem0/Zep.
3. **Lower the evaluation cost.** English-first quickstart, ~5 core commands
   surfaced, governance vocabulary moved to an advanced doc, and a
   one-paragraph "use this if / don't use this if" naming the niche (offline +
   audit-history-matters + Claude-Code-resident) — telling the median user to use
   `CLAUDE.md` instead.

---

## What changed in response

The three conditions were treated as release blockers and addressed before the
first public release:

- **Ship clean and gate it.** The derived-surface drift was fixed (the wiki sync
  now self-cleans obsolete/unpublishable pages), and the authoring instance
  passes its own integrity checks (`doctor` / `wiki-lint` / runtime-parity),
  enforced by a pre-commit hook and a cross-platform CI matrix (Linux/macOS/
  Windows × Python 3.8/3.11/3.13).
- **Pitch rewritten to the surviving truth.** The README and
  [comparison.md](comparison.md) lead with the append-only, source-attributed,
  queryable decision ledger and explicitly disclaim semantic consolidation,
  cross-runtime sync, and recall-quality parity with embedding/graph systems.
- **Lower evaluation cost.** English-first docs, a small core-command quickstart
  (`init` / `file` / `search` / `supersede` / `session-start`), governance
  vocabulary moved to advanced docs, and a "use this if / don't use this if"
  section that points the median user to `CLAUDE.md` instead.

One honest nuance the evaluation surfaced: the "append-only" guarantee is
enforced by the CLI's interface discipline, not by the database itself *by
default* — a direct SQLite session could otherwise rewrite history. As of
v0.1.2 you can opt into true database-level enforcement with `kb.py harden`
(SQLite triggers). See the
[integrity model](concepts.md#integrity-model-how-append-only-is-enforced).

---

## Appendix — full debate transcript

<details>
<summary>Opening statements, two rebuttal rounds, and closings</summary>

### Opening — Adversarial
KB Factory is a real, executable memory runtime — not process theater. The code
confirms typed records, FTS5 + LIKE fallback search (`records.py:201`),
supersession-not-overwrite semantics (`cmd_supersede`), provenance via
`source_id` FK enforcement, and a genuinely append-only audit trail. But *given
the alternatives* the case is weaker than the marketing claims: the headline
value (durable memory, short always-loaded layer, consolidation) substantially
overlaps with the in-box stack (CLAUDE.md + auto-memory + the `consolidate-memory`
skill); `consolidate` is exact-title dedupe + date demotion, not semantic; there
are no embeddings/graph (keyword FTS loses on paraphrased recall); and the
authoring repo shows 40 lint issues, 14 stale pages, 2 hash mismatches, and
live/template drift. **Top 5 concerns:** (1) redundancy vs the free in-box stack;
(2) "consolidate/curate" oversold; (3) self-inflicted unreliability; (4)
keyword-only retrieval; (5) adoption friction + lock-in.

### Opening — Hostile
"A filing cabinet for one." Strip the vocabulary and it's CLAUDE.md + a SQLite
notes table + a manual `consolidate` verb that Anthropic ships automatically
(Auto Dream). Typed records/tiers/supersession is a librarian's workflow imposed
on a coding session, and the repo proves nobody maintains it (40 lint issues,
etc.). `git log`: few dozen commits, one author, weeks, zero external users. Three
byte-identical runtime copies guarded by a parity test that already caught drift.
No moat vs Mem0 (~48k★)/Zep/Letta; fallback search is `LIKE '%query%'`. **5
reasons nobody should use it:** manual reimplementation of in-box features;
unsustainable discipline; zero users; can't keep its own runtime copies in sync;
no moat.

### Opening — Advocate
The comparators solve *recall*; KB Factory solves *project epistemics* — a typed,
auditable, token-budgeted account of decisions/premises/open-questions that
survives across conversations and runtimes. **5 differentiators:** (1) genuinely
stdlib-only/offline/single-file; (2) typed records with mechanically-enforced
non-destruction (`update` refuses meaning change `records.py:230`; `supersede`
links + marks `SUPERSEDIDO` `records.py:247-285`); (3) token-budgeted always-on
tier (NOW/HOT capped); (4) provenance chain with hash-drift verification; (5) one
canonical store, multiple agent surfaces. Honest limits conceded: live/template
drift, stale wiki, mechanical consolidate.

### Rebuttal R1 — Adversarial
Concedes supersession + provenance as the honest core. The "moat" point is the
weakest dressed as strongest — the derived surfaces demonstrably disagree in this
repo. The token-budget point bounds the export, not the session. Offline is
granted, but it's a deployment property and buys the recall ceiling. Sharpened:
value relocates from "intelligent memory" to "auditable ledger" — but a ledger
whose derived views are unreconciled is one you can't trust at the moment you'd
consult it.

### Rebuttal R1 — Hostile
Dismantles the moat: it's one store + N derived copies that drift; a stale derived
surface is a cache-invalidation problem the user now owns. Cowork/claude.ai don't
read the store — they get a flat `PROJECT_PACK.md` + session wrappers. So it's
"one live store + two hand-exported snapshots" = CLAUDE.md that pretends the
snapshot is synchronized. Adds a synchronization obligation rather than removing
one.

### Rebuttal R1 — Advocate
Concedes (1) unreliability — fix = make `doctor`/parity/`wiki-lint` a CI release
gate (the detector working *is* the differentiator); (2) consolidate oversold —
fix = one doc edit (the spec already mandates the honesty); (3) keyword retrieval
— a scope choice, stdlib-only is the value prop. Undefeated: the supersession
invariant is the architectural inverse of the comparators; token-budgeted load is
measurable; one store / multiple surfaces.

### Rebuttal R2 (crux) — Adversarial
The over-Anthropic case reduces to one mechanism: non-destructive supersession (+
FK provenance), the inverse of `consolidate-memory`. Everything else collapses vs
the in-box stack (Auto Dream automatic; consolidate does more; cross-runtime is a
liability). Merit: yes, narrowly; insufficient to justify the full runtime for all
but the audit-obsessed.

### Rebuttal R2 (crux) — Hostile
The ledger's value is conditional on freshness, which is what fails. CLAUDE.md is
git-versioned, so `git log`/`git blame` already reconstruct belief history
non-destructively — a feature git shipped in 2005. The in-box stack wins on the
only axis that matters: it *runs* (automatic), whereas KB Factory depends on a
human remembering to file/consolidate/export. Verdict: no real value added;
what's unique is manual overhead.

### Rebuttal R2 (crux) — Advocate (closing)
The in-box stack is lossy *by design*; KB Factory is non-destructive *by design*
— architectural opposites, enforced in code (`records.py:230`, `247-285`). You
cannot get an append-only ledger by configuring a consolidator. For any project
where a wrong premise compounds, "when did this stop being true and what
overturned it?" is the most expensive question and the one the in-box stack
structurally cannot answer. The hygiene debts are "the detector working" — only
KB Factory can mechanically tell you its memory rotted.

</details>
