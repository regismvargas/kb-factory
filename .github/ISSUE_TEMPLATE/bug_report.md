---
name: Bug report
about: Report a defect in KB Factory
title: "[bug] "
labels: bug
---

**What happened**
A clear description of the bug.

**Expected behavior**
What you expected instead.

**Reproduction**
Steps or a minimal command sequence, e.g.:
```bash
python .kb/kb.py init
python .kb/kb.py create --category DECISAO --domain x --title "..." --content "..."
# ...
```

**Environment**
- OS:
- Python version (`python --version`):
- KB Factory version / commit:

**Diagnostics (if relevant)**
Output of `python .kb/kb.py doctor --json` and/or `python .kb/kb.py wiki-lint --json`.

**Notes**
Anything else (logs, screenshots). Do not paste secrets or private knowledge-base content.
