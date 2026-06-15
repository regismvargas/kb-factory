# KB Factory vs. other memory systems

> **Scope & honesty note.** This page exists so you can decide *whether KB
> Factory is the right tool for you* — not to win an argument. Every comparison
> below is meant to be fair. Competitor facts are sourced; figures marked
> `⚠︎verify` should be re-checked against the vendor's own docs before this page
> is published (see [Sources](#sources)). If something here is wrong, please
> open an issue.

## TL;DR positioning

> **Where Anthropic's memory stack is consolidative by design — it improves the
> current snapshot by overwriting the past — KB Factory is append-only by
> design: every superseded decision stays as a linked, source-attributed row, so
> you can mechanically reconstruct what the project believed at any past point
> and exactly what overturned it.** It runs entirely on the Python standard
> library and SQLite — no service, no vector database, no API key.

This positioning was stress-tested in an adversarial/hostile moderated debate
(see [merit-evaluation.md](merit-evaluation.md)); it is the one claim that
survived. If you want a hosted memory layer, a vector store, semantic recall, or
an autonomous-agent runtime, the projects below are a better fit. If you want
your *codebase's* decisions, premises, facts, open items, and learnings to
persist as an **auditable, queryable belief history** — and you value zero
infrastructure — that is what KB Factory is for.

### What KB Factory does *not* claim

To stay honest (and because each of these was dismantled under hostile review):

- **Not** "intelligent/semantic consolidation." `consolidate` is mechanical
  (exact lowercased-title dedupe + date-based tier demotion); semantic merge is
  the operator's/LLM's job.
- **Not** a "synchronized cross-runtime store." There is one canonical SQLite
  store; the Cowork/claude.ai surfaces are **point-in-time exports**, not a live
  sync, and can go stale if not regenerated.
- **Not** recall-quality parity with embedding/graph systems. Retrieval is
  lexical (SQLite FTS5); paraphrased/relational recall loses to Mem0/Zep/Cognee.
- **Not** for the median user. If you don't need an auditable belief *history*,
  `CLAUDE.md` + auto-memory is the simpler correct choice.

---

## The landscape

There are two families of "AI memory" projects, and KB Factory sits at an angle
to both.

### Family A — Anthropic's own memory features

| Feature | What it is | Relationship to KB Factory |
|---|---|---|
| **Memory tool** (API, beta since 2025‑09) | A low-level primitive: Claude can create/read/update/delete files in a memory directory **you** host, persisting across conversations. | **Complementary, lower layer.** It's a file-CRUD primitive with no schema, no typing, no governance. KB Factory is the *discipline* you'd otherwise have to invent on top of it. |
| **Memory on Claude Managed Agents** (public beta, 2026) | Hosted: agents learn from past sessions and share learnings, with audit trails / rollback / redact. | **Different deployment model.** Hosted & account-scoped vs. local & project-scoped. Strong if you live inside managed agents; KB Factory is for local, repo-owned memory. |
| **Claude Code native memory** | `CLAUDE.md` (explicit rules) + auto-memory (learned patterns) + **"Auto Dream"** background consolidation of memory files. | **Closest overlap, and the honest one to address.** KB Factory adds typed records, query/filtering, supersession, provenance, and tiered loading that flat `CLAUDE.md`/auto-memory don't provide. |
| **`consolidate-memory` skill** | A reflective pass that merges duplicates, fixes stale facts, prunes the index. | **Direct conceptual parallel** to KB Factory's `consolidate` / `doctor` / `hygiene-audit` — but over free-form memory files rather than a typed, queryable store. |

**Takeaway:** Anthropic gives you a *primitive* (the memory tool), a *hosted
product* (managed-agent memory), and *lightweight conventions* (CLAUDE.md +
auto-memory + a consolidation skill). None of them impose an auditable,
queryable, typed data model on your project's knowledge. That gap is KB
Factory's reason to exist.

### Family B — third-party agent-memory frameworks

| Project | Core idea | Storage / deps | How KB Factory differs |
|---|---|---|---|
| **Mem0** (~48k★ `⚠︎verify`) | A memory *layer* you bolt onto an agent; extracts & recalls salient facts. | Vector DB + LLM extraction; hosted option. | KB Factory is zero-dep, local-first, **typed & governed**, project-scoped — not a per-user recall layer. |
| **Letta / MemGPT** | An OS-inspired *runtime* where the agent manages its own memory like paging RAM. | Service/runtime; DB-backed. | KB Factory is not a runtime and does not own the agent loop; it's a passive, inspectable store the agent queries via a CLI. |
| **Zep** | Builds a **temporal knowledge graph** from conversation; strong long-memory benchmarks (`⚠︎verify`). | Service + graph/vector store. | KB Factory has no graph and no service; it favors typed records + FTS + human-readable exports over an automatic KG. |
| **Cognee** | Builds a **knowledge graph from documents** for deep retrieval. | Graph/vector pipeline + deps. | Different goal (document KG / RAG) vs. curated project decision/learning memory. |

**Takeaway:** these are powerful, but they are *services or runtimes* with
external dependencies (vector/graph stores, sometimes cloud). KB Factory
deliberately refuses all of that to stay portable, offline, auditable, and
cheap.

---

## Capability matrix

| Dimension | KB Factory | Anthropic Memory tool | Claude Code native memory | Mem0 | Zep / Letta / Cognee |
|---|---|---|---|---|---|
| Runtime dependencies | **None (Python stdlib)** | Host-provided | Built into client | Vector DB + LLM | Service + store |
| Runs fully offline | **Yes** | Depends on host | Partially | No (typically) | Mostly no |
| Storage | **SQLite + FTS5, single file** | Files you host | Markdown files | Vector DB | Graph/vector DB |
| Memory scope | **Per project / repo** | App-defined | Per project (CLAUDE.md) + user | Per user/agent | Per user/agent/session |
| Typed records | **Yes** (decision/premise/fact/open-item/learning) | No | No | Partial (facts) | Varies |
| Versioning model | **Supersession (never overwrite)** | Overwrite | Overwrite/append | Update/replace | Temporal (Zep) |
| Provenance / audit trail | **Yes** (source→record→export→session + op log) | Change log (managed) | Limited | Limited | Varies |
| Bounded always-loaded snapshot | **Yes** — NOW/HOT export is capped (bounds the *export*, not the live session) | No | Partial | N/A | N/A |
| Governance ops (consolidate/doctor/audit) | **Mechanical**, built-in (dedupe + tier demotion + integrity checks; not semantic) | `consolidate-memory` skill | Auto Dream + skill | Manual | Service-managed |
| Multi-runtime surfaces | One store → Code plugin + **point-in-time exports** for Cowork / claude.ai (not live sync) | API-scoped | Claude Code | SDK-scoped | SDK-scoped |
| Hosting / ops burden | **None** | You host the store | None | DB to run/pay | Service to run/pay |

*(Cells for non-KB tools are summarized from public material and should be
re-verified per the honesty note before publication.)*

---

## When to use which

**Reach for KB Factory when:**
- You want a project's **decisions, premises, facts, open items, and learnings**
  to persist and stay auditable across conversations *and* across agents.
- You want **zero infrastructure** — no DB to run, no key, works offline, backs
  up as one SQLite file.
- You value **discipline over magic**: typed records, supersession instead of
  silent overwrite, a thin always-loaded context, and explicit consolidation.

**Prefer something else when:**
- You need **per-user chatbot recall** at scale → Mem0.
- You need an **autonomous agent that runs for days** managing its own memory →
  Letta/MemGPT.
- You need a **temporal knowledge graph** or **document-RAG knowledge graph** →
  Zep / Cognee.
- You're fully inside **managed agents** and want hosted, account-scoped memory
  → Anthropic Managed-Agent memory.

**Use KB Factory *with* Anthropic's memory tool, not instead of it:** let the
memory tool be the persistence primitive and let KB Factory impose the schema,
typing, and governance on top.

---

## Gaps this comparison exposes (candidate v1 backlog)

These are honest weaknesses surfaced by lining KB Factory up against the field.
They feed feature add/cut decisions for v1:

1. **No semantic retrieval out of the box.** FTS5 is lexical; competitors lean
   on embeddings. Decide whether to document this as a deliberate choice
   (offline, zero-dep) or offer an optional embeddings adapter.
2. **No automatic extraction.** KB Factory expects the agent to *file* records;
   Mem0/Zep auto-extract. This is a feature (curation, not noise) but must be
   framed as such, not hidden.
3. **Benchmarks.** Competitors cite LongMemEval-style numbers. KB Factory has
   none; consider a small, honest task-continuity demonstration rather than a
   contrived benchmark claim.
4. **Cross-agent continuity proof.** The cross-conversation/cross-agent claim
   needs a concrete, reproducible demo (see [provenance-and-continuity.md](provenance-and-continuity.md)).

---

## Sources

- Anthropic Memory tool — Claude Docs: <https://console.anthropic.com/docs/en/agents-and-tools/tool-use/memory-tool>
- Anthropic, "Memory" announcement: <https://www.anthropic.com/news/memory>
- Mem0 / Zep / Letta / Cognee comparison (secondary, `⚠︎verify` figures): industry comparison roundups, 2026.

> Before publishing: replace `⚠︎verify` figures with vendor-sourced numbers (or
> remove the number and keep the qualitative point), and re-read each
> competitor's current docs so no claim is stale.
