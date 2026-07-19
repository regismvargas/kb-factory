---
description: Route a new project into KB alone or KB plus Wiki without inventing scope.
allowed-tools: Read, Write, Edit, Bash, Grep, Glob
---

Start a new project with KB/Wiki vNext.

Use this command for a fresh workspace that needs both classic `.kb/` bootstrap
and vNext activation. Do not fabricate project scope; ask the user for the
minimum project name/domain details if they are missing.

1. If `.kb/` is absent, copy the stand-alone bundle `classic-template/.kb/`
   into the project as `.kb/`.
2. Choose the activation command:
   - `new-project-init-kb-alone` for memory without wiki publication.
   - `new-project-init-kb-wiki` when the user explicitly wants KB + Wiki.
3. Run `new-project-verify-install`.
4. Report the created surfaces and the first recommended session command.
