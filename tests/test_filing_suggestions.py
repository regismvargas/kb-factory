"""WP-KBF.18: session-start advisory filing suggestions.

Tests build_filing_suggestions() output shape, advisory (non-enforcing) mode,
alignment with when_to_file / provenance_expectations, and lifecycle integration.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


REPO = Path(__file__).resolve().parent.parent
KB_PY = REPO / "core" / "templates" / "kb" / "kb.py"
LIVE_RUNTIME = REPO / "core" / "templates" / "kb" / "runtime"

VALID_TYPES = {"answer", "analysis", "synthesis"}
VALID_BANDS = {"high", "review"}
VALID_ACTIONS = {"file", "review", "skip"}


def _base_config(**overrides) -> dict:
    cfg = {
        "schema_version": 4,
        "project": {"name": "Suggestions KB", "slug": "suggestions-kb", "primary_repo_path": ".", "kb_root": "."},
        "domains": ["test_domain"],
        "hot_session_limit": 10,
        "memory": {"now_path": "memory/NOW.md", "index_path": "memory/INDEX.md", "hot_path": "memory/HOT.md", "topics_dir": "memory/topics"},
        "exports": {"cowork_dir": "exports/cowork", "claude_ai_dir": "exports/claude-ai"},
        "retention": {"premise_review_days": 14, "hot_review_days": 7, "cold_after_days": 90},
        "lifecycle": {"events": {"session_start": {"run_audit": False, "apply_demotions": False, "refresh_exports": False, "run_wiki_check": False, "run_wiki_lint": False, "run_wiki_sync": False}}},
        "agent_protocol": {"consult_before_assuming": True, "verify_sensitive_facts": True, "prefer_supersede_over_update": True, "keep_loaded_memory_short": True},
        "wiki": {
            "enabled": False,
            "activation_mode": "manual",
            "project_profile": None,
            "page_types": [],
            "eligibility": {"min_active_records": 30, "min_domains_with_records": 2, "min_soft_signal_score": 1},
            "semantic": {"min_confidence_autopublish": 0.8, "min_confidence_review": 0.55},
            "renderers": {"mkdocs": {"enabled": False, "site_name": "Test Wiki"}},
        },
    }
    cfg.update(overrides)
    return cfg


@pytest.fixture(scope="module")
def suggestions_kb(tmp_path_factory):
    kb_dir = tmp_path_factory.mktemp("suggestions_kb")
    shutil.copytree(LIVE_RUNTIME, kb_dir / "runtime")
    (kb_dir / "kb.config.json").write_text(json.dumps(_base_config()), encoding="utf-8")
    shutil.copy2(KB_PY, kb_dir / "kb.py")
    subprocess.run(
        [sys.executable, str(kb_dir / "kb.py"), "init"],
        capture_output=True, text=True, check=True, cwd=str(kb_dir),
    )
    return kb_dir


def _run_json(kb_dir, *args):
    r = subprocess.run(
        [sys.executable, str(kb_dir / "kb.py")] + list(args) + ["--json"],
        capture_output=True, text=True, check=True, cwd=str(kb_dir),
    )
    return json.loads(r.stdout)


def _run(kb_dir, *args, check=True):
    return subprocess.run(
        [sys.executable, str(kb_dir / "kb.py")] + list(args),
        capture_output=True, text=True, check=check, cwd=str(kb_dir),
    )


# --------------------------------------------------------------------------
# Unit-level: build_filing_suggestions shape and semantics
# --------------------------------------------------------------------------

class TestBuildFilingSuggestionsUnit:
    """Direct unit tests against build_filing_suggestions() in the live runtime."""

    def _import(self):
        sys.path.insert(0, str(LIVE_RUNTIME.parent))
        try:
            from runtime.filing_policy import build_filing_suggestions, get_filing_policy
            return build_filing_suggestions, get_filing_policy
        finally:
            sys.path.pop(0)

    def test_suggestion_objects_have_required_keys(self):
        build_filing_suggestions, get_filing_policy = self._import()
        policy = get_filing_policy({})
        counts = {"active_records": 5, "hot_records": 2, "open_pendencias": 1}
        suggestions = build_filing_suggestions(policy, counts)
        assert isinstance(suggestions, list)
        for s in suggestions:
            assert "type" in s, f"missing 'type' in {s}"
            assert "reason" in s, f"missing 'reason' in {s}"
            assert "confidence_band" in s, f"missing 'confidence_band' in {s}"
            assert "recommended_action" in s, f"missing 'recommended_action' in {s}"

    def test_suggestion_field_values_are_valid(self):
        build_filing_suggestions, get_filing_policy = self._import()
        policy = get_filing_policy({})
        counts = {"active_records": 5, "hot_records": 2, "open_pendencias": 1}
        suggestions = build_filing_suggestions(policy, counts)
        for s in suggestions:
            assert s["type"] in VALID_TYPES, f"unexpected type: {s['type']}"
            assert s["confidence_band"] in VALID_BANDS, f"unexpected band: {s['confidence_band']}"
            assert s["recommended_action"] in VALID_ACTIONS, f"unexpected action: {s['recommended_action']}"
            assert isinstance(s["reason"], str) and s["reason"], "reason must be non-empty string"

    def test_empty_kb_produces_empty_suggestions(self):
        """Zero active records, hot records, and open pendencias → no suggestions."""
        build_filing_suggestions, get_filing_policy = self._import()
        policy = get_filing_policy({})
        counts = {"active_records": 0, "hot_records": 0, "open_pendencias": 0}
        suggestions = build_filing_suggestions(policy, counts)
        assert suggestions == []

    def test_suggestions_grounded_in_when_to_file(self):
        """Reason strings must come from policy when_to_file or provenance_expectations."""
        build_filing_suggestions, get_filing_policy = self._import()
        policy = get_filing_policy({})
        counts = {"active_records": 3, "hot_records": 1, "open_pendencias": 2}
        suggestions = build_filing_suggestions(policy, counts)
        when_to_file = policy["when_to_file"]
        prov = policy["provenance_expectations"]
        valid_reasons = set(when_to_file) | set(prov.values())
        for s in suggestions:
            assert s["reason"] in valid_reasons, (
                f"Suggestion reason not grounded in policy: '{s['reason']}'"
            )

    def test_advisory_mode_not_enforcing(self):
        """build_filing_suggestions must never modify enforcement_mode."""
        build_filing_suggestions, get_filing_policy = self._import()
        policy = get_filing_policy({})
        original_mode = policy["enforcement_mode"]
        counts = {"active_records": 10, "hot_records": 5, "open_pendencias": 3}
        build_filing_suggestions(policy, counts)
        # Policy dict must not be mutated
        assert policy["enforcement_mode"] == original_mode == "advisory"


# --------------------------------------------------------------------------
# Integration: session-start JSON includes filing_suggestions
# --------------------------------------------------------------------------

class TestSessionStartFilingSuggestions:
    """Verify filing_suggestions appears in session-start --json output."""

    def test_session_start_json_includes_filing_suggestions_key(self, suggestions_kb):
        # Seed one record so counts > 0
        _run(suggestions_kb, "file", "--filing-type", "answer", "--category", "APRENDIZADO",
             "--domain", "test_domain", "--title", "seed", "--content", "seed content",
             "--confidence", "0.9", "--json")
        result = _run_json(suggestions_kb, "lifecycle", "session-start")
        assert "filing_suggestions" in result, (
            "'filing_suggestions' key missing from session-start output"
        )

    def test_filing_suggestions_is_list(self, suggestions_kb):
        result = _run_json(suggestions_kb, "lifecycle", "session-start")
        assert isinstance(result["filing_suggestions"], list)

    def test_filing_suggestions_items_have_required_shape(self, suggestions_kb):
        result = _run_json(suggestions_kb, "lifecycle", "session-start")
        for s in result["filing_suggestions"]:
            assert s.get("type") in VALID_TYPES
            assert s.get("confidence_band") in VALID_BANDS
            assert s.get("recommended_action") in VALID_ACTIONS
            assert isinstance(s.get("reason"), str) and s["reason"]

    def test_existing_keys_unchanged(self, suggestions_kb):
        """Adding filing_suggestions must not remove or reshape existing result keys."""
        result = _run_json(suggestions_kb, "lifecycle", "session-start")
        for key in ("event", "generated_at", "event_config", "paths", "counts", "actions_run"):
            assert key in result, f"Expected existing key '{key}' missing from result"


# --------------------------------------------------------------------------
# Parity
# --------------------------------------------------------------------------

class TestFilingSuggestionsParity:
    def test_live_core_template_filing_policy_modules_match(self):
        core = (REPO / "core" / "runtime" / "filing_policy.py").read_text(encoding="utf-8")
        template = (REPO / "core" / "templates" / "kb" / "runtime" / "filing_policy.py").read_text(encoding="utf-8")
        assert core == template, "filing_policy.py: core/runtime != core/templates/kb/runtime"

    def test_live_core_template_lifecycle_modules_match(self):
        core = (REPO / "core" / "runtime" / "lifecycle.py").read_text(encoding="utf-8")
        template = (REPO / "core" / "templates" / "kb" / "runtime" / "lifecycle.py").read_text(encoding="utf-8")
        assert core == template, "lifecycle.py: core/runtime != core/templates/kb/runtime"
