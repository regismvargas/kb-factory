# KB Index

- Initialize once with `python .kb/kb.py init --name "<Project Title>" --slug <project-slug> --domains <a,b,c> --seed .kb/seed/initial_records.jsonl`. It renders the `{{...}}` placeholders and prefixes record IDs with the slug.
- Read `.kb/memory/NOW.md`, then `.kb/memory/HOT.md` at the start of each session.
- Use `.kb/memory/INDEX.md` only when you need the broader map.
- Use `.kb/memory/topics/` for short domain slices.
- Turn the derived wiki on with `python .kb/kb.py wiki-config --enable`; lifecycle events then keep `.kb/wiki/live` current.
