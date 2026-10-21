"""E4.6 dense list: the optional extra stays out of the core, the derived index
never touches the classic KB, and the list fuses through the E1.1 provider seam.

Every test here runs on the standard library: a stub embedder stands in for
model2vec, and the scoring falls back to plain Python without numpy. One
`full`-tier test exercises the real model when the extra and the pinned model
are already on the machine.
"""
from __future__ import annotations

import contextlib
import hashlib
import importlib.util
import io
import json
import math
import sqlite3
import subprocess
import sys
import textwrap
from array import array
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
KB_NEXT = REPO_ROOT / "core" / "versions" / "kb-wiki-vnext" / "runtime" / "kb_next.py"


def load_kb_next():
    spec = importlib.util.spec_from_file_location("kb_next_dense_under_test", KB_NEXT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


kb_next = load_kb_next()

RECORDS = [
    # id, category, title, content, tags
    ("DEC-GATE", "DECISAO", "Gate humano na escrita", "Toda escrita canonica passa pelo gate humano.", ["governanca"]),
    ("FAT-DESPESA", "FATO", "Despesa mensal de nuvem", "A despesa de nuvem fica abaixo do teto.", ["financas"]),
    ("LRN-WORKTREES", "APRENDIZADO", "Worktrees compartilham a KB", "Sessoes em worktrees leem o banco principal.", []),
]
# The stub's notion of meaning: words in one group share a vector direction.
SYNONYMS = {"custo": "despesa", "gasto": "despesa", "despesa": "despesa", "nuvem": "nuvem", "cloud": "nuvem"}
DIM = 16


class StubEmbedder:
    """Deterministic bag-of-concepts vectors; pure Python, no numpy."""

    name = "potion-base-32M"
    dim = DIM
    library = "stub"

    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    def embed(self, texts: list[str]) -> list[bytes]:
        self.calls.append(list(texts))
        out = []
        for text in texts:
            vector = [0.0] * DIM
            for word in text.lower().replace(".", " ").split():
                concept = SYNONYMS.get(word, word)
                vector[int(hashlib.sha256(concept.encode()).hexdigest(), 16) % DIM] += 1.0
            norm = math.sqrt(sum(value * value for value in vector)) or 1.0
            out.append(array("f", [value / norm for value in vector]).tobytes())
        return out


def make_kb(root: Path) -> Path:
    memory = root / ".kb" / "memory"
    memory.mkdir(parents=True)
    (memory / "HOT.md").write_text("# HOT\n", encoding="utf-8")
    (memory / "INDEX.md").write_text("# INDEX\n", encoding="utf-8")
    db = root / ".kb" / "kb.db"
    with contextlib.closing(sqlite3.connect(db)) as conn:
        conn.execute(
            "CREATE TABLE records (id TEXT PRIMARY KEY, category TEXT NOT NULL, domain TEXT NOT NULL, "
            "title TEXT NOT NULL, content TEXT NOT NULL, status TEXT NOT NULL, tier TEXT NOT NULL, "
            "source TEXT NOT NULL, tags_json TEXT NOT NULL DEFAULT '[]', created_at TEXT NOT NULL, "
            "updated_at TEXT NOT NULL, source_id TEXT)"
        )
        conn.executemany(
            "INSERT INTO records VALUES (?, ?, 'architecture', ?, ?, 'ATIVO', 'WARM', 'test', ?, "
            "'2026-03-01T09:00:00Z', '2026-03-01T09:00:00Z', NULL)",
            [(rid, category, title, content, json.dumps(tags)) for rid, category, title, content, tags in RECORDS],
        )
        conn.commit()
    return db


def run_kb_next(root: Path, *argv: str) -> tuple[int, str, str]:
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = kb_next.main(["--project-root", str(root), *argv])
    return code, out.getvalue(), err.getvalue()


def set_dense(root: Path, **values) -> None:
    path = root / ".kb-next" / "kb-next.config.json"
    config = json.loads(path.read_text(encoding="utf-8"))
    config.setdefault("retrieval", {}).setdefault("dense", {}).update(values)
    path.write_text(json.dumps(config), encoding="utf-8")


def lookup(root: Path, query: str, *extra: str) -> dict:
    code, out, err = run_kb_next(root, "lookup", "--facet", "status", "--query", query, "--json", *extra)
    assert code == 0, err
    return json.loads(out)


def dense_index(root: Path, *extra: str) -> dict:
    code, out, err = run_kb_next(root, "dense-index", "--json", *extra)
    assert code == 0, err
    return json.loads(out)


@pytest.fixture
def project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    make_kb(tmp_path)
    code, _out, err = run_kb_next(tmp_path, "activation-wizard", "--mode", "short", "--choice", "kb-alone", "--json")
    assert code == 0, err
    monkeypatch.setenv(kb_next.DENSE_MODEL_CACHE_ENV, str(tmp_path.parent / f"{tmp_path.name}-models"))
    return tmp_path


@pytest.fixture
def stub(monkeypatch: pytest.MonkeyPatch) -> StubEmbedder:
    embedder = StubEmbedder()
    monkeypatch.setattr(kb_next, "load_dense_embedder", lambda _root, _settings: embedder)
    return embedder


def kb_sha(root: Path) -> str:
    return hashlib.sha256((root / ".kb" / "kb.db").read_bytes()).hexdigest()


# ---------------------------------------------------------------------------
# The extra stays out of the core
# ---------------------------------------------------------------------------


def test_default_lookup_never_imports_the_dense_extra(tmp_path: Path) -> None:
    """Fails if the core imports numpy or model2vec on load or on a default lookup.

    Both names are blocked before the runtime loads, so any import attempt
    raises, and the run also checks they never reached `sys.modules`.
    """
    make_kb(tmp_path)
    script = textwrap.dedent(
        f"""
        import contextlib, importlib.util, io, json, sys
        sys.modules["numpy"] = None
        sys.modules["model2vec"] = None
        spec = importlib.util.spec_from_file_location("kb_next_probe", {str(KB_NEXT)!r})
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        root = {str(tmp_path)!r}
        with contextlib.redirect_stdout(io.StringIO()):
            assert module.main(["--project-root", root, "activation-wizard", "--mode", "short", "--choice", "kb-alone", "--json"]) == 0
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            assert module.main(["--project-root", root, "lookup", "--facet", "status", "--query", "despesa", "--json"]) == 0
        result = json.loads(out.getvalue())
        loaded = [name for name in ("numpy", "model2vec") if sys.modules.get(name) is not None]
        print(json.dumps({{"lists": result["retrieval"]["lists"], "ids": [r["id"] for r in result["results"]], "loaded": loaded}}))
        """
    )
    completed = subprocess.run([sys.executable, "-B", "-c", script], capture_output=True, text=True, check=False)
    assert completed.returncode == 0, completed.stderr
    payload = json.loads(completed.stdout.strip().splitlines()[-1])
    assert payload == {"lists": ["words"], "ids": ["FAT-DESPESA"], "loaded": []}


def test_the_dense_list_is_off_by_default(project: Path) -> None:
    config = json.loads((project / ".kb-next" / "kb-next.config.json").read_text(encoding="utf-8"))

    assert config["retrieval"]["dense"] == kb_next.DENSE_DEFAULTS
    assert config["retrieval"]["dense"]["enabled"] is False
    assert kb_next.ranked_list_names(config) == ["words"]
    assert kb_next.configured_ranked_list_providers(project, config) is None


def test_dense_enabled_without_the_extra_ranks_by_words_and_says_how_to_install(
    project: Path, stub: StubEmbedder, monkeypatch: pytest.MonkeyPatch
) -> None:
    dense_index(project)
    set_dense(project, enabled=True)
    monkeypatch.undo()  # back to the real loader, with the extra blocked
    monkeypatch.setenv(kb_next.DENSE_MODEL_CACHE_ENV, str(project.parent / f"{project.name}-models"))
    monkeypatch.setitem(sys.modules, "model2vec", None)

    result = lookup(project, "custo")

    retrieval = result["retrieval"]
    assert retrieval["lists"] == ["words"]
    assert any(kb_next.DENSE_EXTRA_REQUIREMENT in warning for warning in retrieval["warnings"])
    assert result["results"] == []


def test_dense_index_without_the_extra_fails_with_the_install_hint(project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "model2vec", None)

    code, _out, err = run_kb_next(project, "dense-index", "--json")

    assert code == 1
    assert f"pip install {kb_next.DENSE_EXTRA_REQUIREMENT}" in err
    assert not (project / ".kb-next" / "index" / "dense" / "manifest.json").exists()


def test_fetch_model_without_the_extra_downloads_nothing(project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "model2vec", None)

    def no_download(url: str, timeout: int):
        raise AssertionError(f"dense-index --fetch-model downloaded {url} before checking the extra")

    monkeypatch.setattr(kb_next.urllib.request, "urlopen", no_download)
    model_dir = kb_next.dense_model_dir(project, "potion-base-32M")

    code, _out, err = run_kb_next(project, "dense-index", "--fetch-model", "--json")

    assert code == 1
    assert f"pip install {kb_next.DENSE_EXTRA_REQUIREMENT}" in err
    assert not model_dir.exists()


# ---------------------------------------------------------------------------
# Derived index
# ---------------------------------------------------------------------------


def test_dense_index_is_derived_and_leaves_the_classic_kb_untouched(project: Path, stub: StubEmbedder) -> None:
    before = kb_sha(project)

    built = dense_index(project)

    assert kb_sha(project) == before
    index_dir = project / ".kb-next" / "index" / "dense"
    assert sorted(path.name for path in index_dir.iterdir()) == ["manifest.json", "vectors.sqlite3"]
    # .kb-next/ is versioned in projects; the derived index ignores itself.
    ignore = (index_dir.parent / ".gitignore").read_text(encoding="utf-8").splitlines()
    assert ignore[-1] == "*"
    manifest = json.loads((index_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["schema"] == kb_next.DENSE_INDEX_SCHEMA
    assert manifest["identity"]["model"] == "potion-base-32M"
    assert manifest["identity"]["revision"] == kb_next.DENSE_MODELS["potion-base-32M"]["revision"]
    assert manifest["identity"]["key_fields"] == ["title", "content", "tags"]
    assert manifest["source"]["access"] == "read_only"
    assert built["records"] == 3 and built["embedded_records"] == 3 and built["reused_records"] == 0
    assert "governanca" in " ".join(stub.calls[0])  # tags are part of the key
    assert last_event(project)["event"] == "dense_index"


def test_dense_index_reuses_unchanged_records_and_rebuild_starts_over(project: Path, stub: StubEmbedder) -> None:
    dense_index(project)

    again = dense_index(project)
    rebuilt = dense_index(project, "--rebuild")

    assert again["embedded_records"] == 0 and again["reused_records"] == 3
    assert rebuilt["embedded_records"] == 3 and rebuilt["reused_records"] == 0


def test_lookup_reports_records_the_index_has_not_seen(project: Path, stub: StubEmbedder) -> None:
    dense_index(project)
    set_dense(project, enabled=True)
    with contextlib.closing(sqlite3.connect(project / ".kb" / "kb.db")) as conn:
        conn.execute("UPDATE records SET content = 'O custo de nuvem subiu.' WHERE id = 'FAT-DESPESA'")
        conn.execute("DELETE FROM records WHERE id = 'LRN-WORKTREES'")
        conn.commit()

    stale = lookup(project, "custo")
    refreshed = dense_index(project)
    fresh = lookup(project, "custo")

    assert any("misses 1 new or edited records" in warning for warning in stale["retrieval"]["warnings"])
    assert refreshed["embedded_records"] == 1 and refreshed["removed_records"] == 1 and refreshed["records"] == 2
    assert not any("misses" in warning for warning in fresh["retrieval"]["warnings"])


def test_an_index_built_with_other_settings_is_not_used(project: Path, stub: StubEmbedder) -> None:
    dense_index(project)
    set_dense(project, enabled=True, chunk_words=8, chunk_stride=8)

    result = lookup(project, "custo")

    assert result["retrieval"]["lists"] == ["words"]
    assert any("built with other settings" in warning for warning in result["retrieval"]["warnings"])


def test_lookup_without_an_index_warns_and_ranks_by_words(project: Path, stub: StubEmbedder) -> None:
    set_dense(project, enabled=True)

    result = lookup(project, "despesa")

    assert result["retrieval"]["lists"] == ["words"]
    assert any("no dense index" in warning for warning in result["retrieval"]["warnings"])
    assert [item["id"] for item in result["results"]] == ["FAT-DESPESA"]


# ---------------------------------------------------------------------------
# Fusion through the provider seam
# ---------------------------------------------------------------------------


def test_enabled_dense_list_finds_a_paraphrase_the_word_list_misses(project: Path, stub: StubEmbedder) -> None:
    dense_index(project)
    words_only = lookup(project, "custo")
    set_dense(project, enabled=True)

    fused = lookup(project, "custo")
    dense_alone = lookup(project, "custo", "--lists", "dense")

    assert words_only["results"] == [] and words_only["retrieval"]["lists"] == ["words"]
    assert fused["retrieval"]["lists"] == ["words", "dense"]
    assert [item["id"] for item in fused["results"]][0] == "FAT-DESPESA"
    assert dense_alone["retrieval"]["lists"] == ["dense"]
    assert [item["id"] for item in dense_alone["results"]][0] == "FAT-DESPESA"
    assert last_event(project)["details"]["retrieval"]["lists"] == ["dense"]


def test_lists_flag_overrides_the_config_and_rejects_unknown_names(project: Path, stub: StubEmbedder) -> None:
    dense_index(project)
    set_dense(project, enabled=True)

    words = lookup(project, "despesa", "--lists", "words")
    with pytest.raises(SystemExit) as exit_info:
        run_kb_next(project, "lookup", "--facet", "status", "--query", "x", "--lists", "vectors", "--json")

    assert words["retrieval"]["lists"] == ["words"]
    assert exit_info.value.code == 2


def test_the_dense_list_honors_the_facet_filter(project: Path, stub: StubEmbedder) -> None:
    dense_index(project)

    result = lookup_facet(project, "decisions", "custo nuvem despesa", "--lists", "dense")

    assert [item["id"] for item in result["results"]] == ["DEC-GATE"]


def test_semantic_candidates_follow_the_configured_lists(project: Path, stub: StubEmbedder) -> None:
    dense_index(project)
    set_dense(project, enabled=True)

    candidates = kb_next.semantic_candidates(project, "status", "custo", 1)

    assert [item["id"] for item in candidates] == ["FAT-DESPESA"]


# ---------------------------------------------------------------------------
# Units
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("words", "width", "stride", "expected"),
    [
        (2, 3, 3, ["w0 w1"]),
        (6, 3, 3, ["w0 w1 w2", "w3 w4 w5"]),
        (7, 3, 3, ["w0 w1 w2", "w3 w4 w5", "w4 w5 w6"]),
        (7, 4, 2, ["w0 w1 w2 w3", "w2 w3 w4 w5", "w3 w4 w5 w6"]),
    ],
)
def test_passages_cover_every_word_and_end_at_the_last_one(words: int, width: int, stride: int, expected: list[str]) -> None:
    text = " ".join(f"w{i}" for i in range(words))

    assert kb_next.dense_passages(text, width, stride) == expected


def test_key_text_joins_title_content_and_tags() -> None:
    assert kb_next.dense_key_text("Titulo", "Corpo", '["a", "b"]') == "Titulo\nCorpo\na b"
    assert kb_next.dense_key_text("Titulo", "", "[]") == "Titulo"


def vector(*values: float) -> bytes:
    norm = math.sqrt(sum(value * value for value in values))
    return array("f", [value / norm for value in values]).tobytes()


def test_record_scores_take_the_best_passage_in_plain_python(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "numpy", None)
    blobs = [("A", 2, vector(1, 0) + vector(0, 1)), ("B", 1, vector(1, 1))]

    scores = kb_next.dense_record_scores(blobs, vector(0, 1), 2)

    assert scores["A"] == pytest.approx(1.0, abs=1e-6)
    assert scores["B"] == pytest.approx(math.sqrt(0.5), abs=1e-6)


def test_numpy_scoring_matches_plain_python(monkeypatch: pytest.MonkeyPatch) -> None:
    pytest.importorskip("numpy")
    blobs = [("A", 2, vector(1, 2, 3) + vector(3, 2, 1)), ("B", 1, vector(0, 1, 0)), ("C", 3, vector(1, 0, 0) * 3)]
    query = vector(1, 1, 0)

    with_numpy = kb_next.dense_record_scores(blobs, query, 3)
    monkeypatch.setitem(sys.modules, "numpy", None)
    plain = kb_next.dense_record_scores(blobs, query, 3)

    assert with_numpy.keys() == plain.keys()
    for key in plain:
        assert with_numpy[key] == pytest.approx(plain[key], abs=1e-6)


def test_dense_settings_reject_an_unknown_model_or_a_bad_window() -> None:
    with pytest.raises(ValueError, match="retrieval.dense.model"):
        kb_next.dense_settings({"retrieval": {"dense": {"model": "contriever"}}})
    with pytest.raises(ValueError, match="chunk_stride"):
        kb_next.dense_settings({"retrieval": {"dense": {"chunk_words": 8, "chunk_stride": 16}}})
    assert kb_next.dense_settings(None) == kb_next.DENSE_DEFAULTS


def test_only_the_multilingual_model_is_marked_not_recommended() -> None:
    assert kb_next.dense_model_advisory("potion-base-32M") is None
    advisory = kb_next.dense_model_advisory("potion-multilingual-128M")
    assert advisory and "not recommended" in advisory and "11.7 s" in advisory
    # Still pinned and still accepted, so an existing multilingual index keeps loading until 0.3.
    assert kb_next.dense_settings({"retrieval": {"dense": {"model": "potion-multilingual-128M"}}})["model"] == (
        "potion-multilingual-128M"
    )
    identity = kb_next.dense_index_identity({**kb_next.DENSE_DEFAULTS, "model": "potion-multilingual-128M"}, DIM)
    assert "recommended" not in json.dumps(identity) and "advisory" not in identity


def test_dense_index_warns_when_the_multilingual_model_is_configured(project: Path, stub: StubEmbedder) -> None:
    assert dense_index(project)["warnings"] == []
    set_dense(project, model="potion-multilingual-128M")

    result = dense_index(project)
    code, text, err = run_kb_next(project, "dense-index")

    assert result["model"] == "potion-multilingual-128M"
    assert [warning for warning in result["warnings"] if "not recommended" in warning]
    assert code == 0, err
    assert "Warning: dense model potion-multilingual-128M is not recommended" in text


def test_lookup_warns_only_when_the_multilingual_dense_list_runs(project: Path, stub: StubEmbedder) -> None:
    set_dense(project, model="potion-multilingual-128M")
    dense_index(project)

    words_only = lookup(project, "despesa")
    set_dense(project, enabled=True)
    fused = lookup(project, "custo")
    set_dense(project, model="potion-base-32M")
    dense_index(project)
    base = lookup(project, "custo")

    def advised(result: dict) -> bool:
        return any("not recommended" in warning for warning in result["retrieval"]["warnings"])

    assert not advised(words_only) and words_only["retrieval"]["lists"] == ["words"]
    assert advised(fused) and fused["retrieval"]["lists"] == ["words", "dense"]
    assert [item["id"] for item in fused["results"]][0] == "FAT-DESPESA"
    assert not advised(base)


def test_the_model_cache_must_live_outside_the_project(project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(kb_next.DENSE_MODEL_CACHE_ENV, str(project / "models"))

    with pytest.raises(kb_next.DenseUnavailable, match="outside the project"):
        kb_next.dense_model_dir(project, "potion-base-32M")


def test_a_download_that_does_not_match_the_pin_installs_nothing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_urlopen(url: str, timeout: int):
        return io.BytesIO(b"not the pinned file")

    monkeypatch.setattr(kb_next.urllib.request, "urlopen", fake_urlopen)
    target = tmp_path / "model"

    with pytest.raises(kb_next.DenseUnavailable, match="pinned SHA-256"):
        kb_next.fetch_dense_model(target, "potion-base-32M")

    assert list(target.iterdir()) == []
    assert kb_next.dense_model_problems(target, "potion-base-32M")


# ---------------------------------------------------------------------------
# The real extra, when this machine has it
# ---------------------------------------------------------------------------


@pytest.mark.full
def test_the_pinned_model_ranks_a_paraphrase_first(project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    pytest.importorskip("model2vec")
    monkeypatch.delenv(kb_next.DENSE_MODEL_CACHE_ENV)
    directory = kb_next.dense_model_dir(project, "potion-base-32M")
    if kb_next.dense_model_problems(directory, "potion-base-32M"):
        pytest.skip("pinned model not in the local cache; run kb_next.py dense-index --fetch-model")
    with contextlib.closing(sqlite3.connect(project / ".kb" / "kb.db")) as conn:
        conn.execute(
            "INSERT INTO records VALUES ('FAT-DOG', 'FATO', 'architecture', 'Pet adoption', "
            "'I adopted a golden retriever puppy last spring.', 'ATIVO', 'WARM', 'test', '[]', "
            "'2026-03-01T09:00:00Z', '2026-03-01T09:00:00Z', NULL)"
        )
        conn.commit()

    dense_index(project)
    result = lookup(project, "which animal lives with me", "--lists", "dense")

    assert [item["id"] for item in result["results"]][0] == "FAT-DOG"


def lookup_facet(root: Path, facet: str, query: str, *extra: str) -> dict:
    code, out, err = run_kb_next(root, "lookup", "--facet", facet, "--query", query, "--json", *extra)
    assert code == 0, err
    return json.loads(out)


def last_event(root: Path) -> dict:
    lines = (root / ".kb-next" / "operations.jsonl").read_text(encoding="utf-8").splitlines()
    return json.loads(lines[-1])
