"""KB Factory — pip-installable installer/CLI for the stdlib-only KB scaffold.

This thin package exists so that `pip install kb-factory` gives you a
`kb-factory` command that can scaffold a project's `.kb/` and refresh its
runtime. The knowledge base itself remains a vendored, stdlib-only `.kb/`
folder inside your project (the canonical store); this package just delivers
and updates it.
"""
from __future__ import annotations

__version__ = "0.1.3"
