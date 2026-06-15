## What this changes

<!-- A short description of the change and why. Link the issue it closes. -->

Closes #

## Checklist

- [ ] `pytest` passes locally.
- [ ] No new **runtime** dependency was added (the runtime is Python standard
      library only). Test-only dev tools are fine.
- [ ] Memory semantics preserved: no code path silently overwrites or deletes
      the *meaning* of a record (use supersede). Derived surfaces stay derived.
- [ ] If I changed the command surface, I updated the docs.
- [ ] If I touched the runtime, scaffold, or wiki generation, I ran
      `python .kb/kb.py doctor` and the runtime-parity test.

## Notes for reviewers

<!-- Anything that needs attention: trade-offs, follow-ups, areas of risk. -->
