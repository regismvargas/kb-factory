---
description: Route a new project into KB alone or KB plus Wiki without inventing scope.
allowed-tools: Read, Write, Edit, Bash, Grep, Glob
---

Start a new project with KB/Wiki vNext.

Use this command for a fresh workspace that needs both the classic `.kb/`
and vNext activation. Do not fabricate project scope: ask the user for the
project title, slug (lowercase, `a-z0-9-`) and initial domains if they are
missing. The slug becomes the record ID prefix (`<SLUG>-KB-...`), which keeps
IDs unambiguous when KBs are merged later.

1. Choose the activation command. The default is KB alone; use KB + Wiki only
   when the user explicitly wants wiki pages:
   - `new-project-init-kb-alone` for memory without wiki publication.
   - `new-project-init-kb-wiki` for memory plus the derived wiki.
2. Both commands install the classic `.kb/` with the runtime subcommand
   `install-classic`, which finds the classic scaffold shipped by the
   kb-lifecycle plugin (or the stand-alone bundle). If it reports that no
   template was found, stop and ask the user to install
   `kb-lifecycle@kb-factory-tools`; do not copy files by hand.
3. Run `new-project-verify-install`.
4. Report the created surfaces, the activation mode and the first
   recommended session command.
