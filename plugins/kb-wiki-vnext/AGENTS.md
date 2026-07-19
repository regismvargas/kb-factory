# KB/Wiki vNext Agent Instructions

Use this package only for projects that have a `.kb-next/` runtime line or are
explicitly piloting KB/Wiki vNext.

Session start is thin:

- Invoke the explicit vNext `vnext-session-start` plugin/slash command when
  the client exposes it. When working in a shell, resolve the runtime —
  `.kb-next/runtime/kb_next.py`, else the plugin-bundled `runtime/kb_next.py`,
  else `core/versions/kb-wiki-vnext/runtime/kb_next.py` (KB Factory authoring
  monorepo) — and run `python <resolved-runtime-path> session-start --json`;
  if no runtime resolves, fall back to classic
  `python .kb/kb.py lifecycle session-start --json`.
- Runtime `session-start` does not write canonical `.kb/`, but appends session
  evidence to `.kb-next/operations.jsonl`.
- Read only `.kb-next/memory/NOW.md` by default.
- Load `.kb/memory/HOT.md`, `.kb/memory/INDEX.md`, wiki pages, and historical
  artifacts only on demand.
- Use targeted `lookup` or `semantic-lookup` before opening broad memory.
- For any planning or execution of vNext development until vNext is 100% developed,
  run runtime `compliance-preflight` after thin vNext session-start and before
  planning or editing. Simple operational use does not require the development
  preflight unless it is part of a development round.

Governance boundaries:

- `.kb/` is canonical durable memory.
- `.kb-next/` stores vNext proposals, manifests, draft wiki pages, materialized
  vNext wiki surfaces, and operations evidence.
- Do not write SQL or edit `.kb/kb.db` directly.
- Do not publish vNext drafts to `.kb/wiki/live`.
- Canonical record changes must go through `.kb/kb.py` or vNext
  `proposal-apply`, which itself calls the classic runtime.
- HOT overflow governance must start read-only. Use
  `python .kb/kb.py hygiene-audit --json` for mechanical health and
  `semantic-hygiene --write-proposals` only for
  `.kb-next` proposal evidence; do not auto-demote based on LLM judgment alone.
