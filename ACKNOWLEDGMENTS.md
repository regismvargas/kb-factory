# Acknowledgments

KB Factory stands on ideas developed openly by others. This page credits that
lineage explicitly. The influences below shaped the **design and vocabulary** of
the project; KB Factory's code is an original, clean-room implementation
(Python standard library + SQLite). No third-party source text or code is
reproduced here — ideas were adapted and are cited, not copied.

## Primary intellectual influences

### Andrej Karpathy — LLM "wiki" / context engineering
KB Factory's two foundational ideas trace to Karpathy's public thinking on
giving LLMs a compiled, interlinked knowledge surface and on **context
engineering** — filling the context window with only what the next step needs.

How it shows up in KB Factory:
- The **compiled, interlinked memory** idea informs the optional *wiki layer*
  (a derived, human-readable surface). Crucially, KB Factory **adapts** this
  rather than adopting it wholesale: typed KB records remain canonical; wiki
  pages are derived, never a replacement for the records.
- **Context engineering** is adopted directly as the **thin always-loaded
  context** model: `NOW.md` first, then on-demand retrieval — never bulk
  loading.

### Carlos Perez ([@IntuitMachine](https://x.com/IntuitMachine)) — harness engineering & memory layers
Carlos Perez's writing on **harness engineering**, externalized memory, and the
separation of **agents / skills / MCPs** shaped how KB Factory frames the
runtime's responsibilities.

How it shows up in KB Factory:
- **Harness engineering (adopted):** the harness — not the model — owns context
  construction, state management, verification, and action boundaries. KB
  Factory's CLI + session lifecycle is exactly such a harness.
- **Agents / skills / MCPs separation (adopted):** agents orchestrate, *skills*
  provide reusable procedural guidance (`SKILL.md`), and MCP/connectors are an
  optional later integration — never the primary interface.
- **Memory-layer separation (adapted):** working / episodic / semantic /
  procedural memory distinctions are used as non-canonical design guidance.

> Naming note: the canonical reference in the project's research record is
> "Carlos Perez" (the [@IntuitMachine](https://x.com/IntuitMachine) handle).
> Earlier informal notes may have written "Claudio Perez"; this is the same
> author and the spelling has been standardized to **Carlos Perez**.

These influences were recorded and reconciled during design under the project's
research-recovery gate; both authors were treated as **benchmarks and
references**, not as substitutes for KB Factory's own typed-record model.

## Platform & tooling

- **Anthropic** — Claude Code, Claude Cowork, and the Claude model family, which
  KB Factory targets as first-class runtimes. KB Factory is designed to
  *complement* Anthropic's memory features, not replace them.
- **SQLite** and the **Python standard library**, which make a zero-dependency,
  local-first, single-file knowledge base practical.

## A note on originality

KB Factory deliberately re-derives its data model, CLI, and storage from first
principles so that it can ship as a dependency-free, auditable, single-file
system. Where an external idea is used, it is named above. If you believe an
attribution is missing or imprecise, please open an issue — we will fix it.
