from __future__ import annotations

from pathlib import Path


KB_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = KB_ROOT / "kb.config.json"
DB_PATH = KB_ROOT / "kb.db"


def memory_path(relative_path: str) -> Path:
    return KB_ROOT / relative_path


def ensure_dirs(config: dict) -> None:
    memory = config["memory"]
    exports = config["exports"]
    for rel in (
        "seed",
        Path(memory["topics_dir"]).as_posix(),
        Path(memory.get("now_path", "memory/NOW.md")).parent.as_posix(),
        Path(memory["index_path"]).parent.as_posix(),
        Path(memory["hot_path"]).parent.as_posix(),
        Path(exports["cowork_dir"]).as_posix(),
        Path(exports["claude_ai_dir"]).as_posix(),
    ):
        (KB_ROOT / rel).mkdir(parents=True, exist_ok=True)
    if "wiki" in config:
        for wiki_rel in ("wiki/live", "wiki/snapshots", "wiki/mkdocs"):
            (KB_ROOT / wiki_rel).mkdir(parents=True, exist_ok=True)
