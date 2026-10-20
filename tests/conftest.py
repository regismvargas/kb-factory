"""Suite-wide safety defaults.

When the suite runs from a linked Git worktree, the classic runtime would
resolve a repository `.kb/` to the main worktree KB. Tests always build their
own temporary KBs, so pin the local scope for every subprocess; tests that
exercise the shared-worktree resolution override it explicitly.
"""

from __future__ import annotations

import os

os.environ.setdefault("KB_FACTORY_WORKTREE_SCOPE", "local")


def pytest_configure(config) -> None:
    # Tests shared with the private workbench carry its tier markers.
    config.addinivalue_line("markers", "fast: quick tier in the private workbench")
    config.addinivalue_line("markers", "full: slow tier in the private workbench")
