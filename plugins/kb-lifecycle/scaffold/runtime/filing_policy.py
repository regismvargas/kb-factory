from __future__ import annotations

import argparse
from typing import Any

from .config import load_config as _load_config


FILING_POLICY_DEFAULTS: dict[str, Any] = {
    "enforcement_mode": "advisory",
    "confidence_bands": {"high": 0.8, "review": 0.55},
    "filing_types": {
        "answer": {
            "allowed_categories": ["FATO", "APRENDIZADO", "DECISAO", "PREMISSA"],
            "requires_source_id": False,
            "min_confidence": 0.55,
        },
        "analysis": {
            "allowed_categories": ["APRENDIZADO", "FATO"],
            "requires_source_id": True,
            "min_confidence": 0.55,
        },
        "synthesis": {
            "allowed_categories": ["FATO", "APRENDIZADO", "DECISAO"],
            "requires_source_id": False,
            "min_confidence": 0.55,
        },
    },
    "when_to_file": [
        "Captures durable insight, decision rationale, or synthesis reusable across sessions.",
        "Distills knowledge from multiple records, sources, or conversation threads.",
        "Losing the content to chat history would be a meaningful loss.",
    ],
    "when_not_to_file": [
        "Transient or one-off lookup.",
        "Already covered by an active KB record - supersede that record instead.",
        "Confidence below review band without explicit operator approval.",
    ],
    "provenance_expectations": {
        "answer": "Explain reasoning basis; link supporting record ids in content when derived.",
        "analysis": "Must carry source_id; reference the summary, not restate it.",
        "synthesis": "List the supporting record ids or source ids that were combined.",
    },
}


# Profile-aware filing deltas. Kept here (not in wiki.PROFILE_PRESETS) so that
# wiki.py does not become a general policy registry. Stubs are empty in this
# slice; real overrides land with the portfolio rollout.
FILING_PROFILE_OVERRIDES: dict[str, dict] = {
    "corporate_companion": {},
    "strategic_framework": {},
    "hybrid_research_ops": {},
}


def _deep_merge(base: dict, overlay: dict) -> dict:
    """Return a new dict where overlay replaces scalar/list values and
    recursively merges nested dicts. Lists are replaced whole (no concat)."""
    out = {k: (v.copy() if isinstance(v, (dict, list)) else v) for k, v in base.items()}
    for k, v in overlay.items():
        if k in out and isinstance(out[k], dict) and isinstance(v, dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v.copy() if isinstance(v, (dict, list)) else v
    return out


def _deep_copy_defaults() -> dict:
    return _deep_merge({}, FILING_POLICY_DEFAULTS)


def get_filing_policy(config: dict) -> dict:
    """Resolve the active filing policy.

    Merge order (later wins):
      1. FILING_POLICY_DEFAULTS
      2. FILING_PROFILE_OVERRIDES[<profile>] when
         wiki.activation_mode == "profile" and wiki.project_profile is set
      3. config["filing_policy"] user overrides

    The returned dict always includes:
      - "enforcement_mode" ("advisory" by default)
      - "resolved_profile" (profile name applied, or None)
    """
    resolved = _deep_copy_defaults()
    resolved["resolved_profile"] = None

    wiki = (config or {}).get("wiki", {}) or {}
    mode = wiki.get("activation_mode")
    profile_name = wiki.get("project_profile")
    if mode == "profile" and profile_name and profile_name in FILING_PROFILE_OVERRIDES:
        profile_overrides = FILING_PROFILE_OVERRIDES[profile_name]
        if profile_overrides:
            resolved = _deep_merge(resolved, profile_overrides)
        resolved["resolved_profile"] = profile_name

    user = (config or {}).get("filing_policy", {}) or {}
    if user:
        resolved = _deep_merge(resolved, user)

    return resolved


def evaluate_filing(policy: dict, filing_type: str, data: dict) -> list[dict]:
    """Return a list of policy violations for a filing attempt.

    Each violation is a dict with keys:
      - field: which record field triggered the violation
      - issue: short machine-readable issue code
      - detail: human-readable explanation

    An empty list means the filing is compliant with the resolved policy.
    Callers decide how to react based on policy["enforcement_mode"].
    """
    violations: list[dict] = []
    filing_types = policy.get("filing_types", {}) or {}
    spec = filing_types.get(filing_type)
    if spec is None:
        violations.append({
            "field": "filing_type",
            "issue": "unknown_filing_type",
            "detail": f"Filing type '{filing_type}' is not recognized by the active policy.",
        })
        return violations

    allowed = set(spec.get("allowed_categories", []) or [])
    if allowed:
        category = data.get("category")
        if category not in allowed:
            violations.append({
                "field": "category",
                "issue": "category_not_allowed",
                "detail": (
                    f"Category '{category}' is not allowed for filing type "
                    f"'{filing_type}'. Allowed: {sorted(allowed)}."
                ),
            })

    min_confidence = spec.get("min_confidence")
    if min_confidence is not None:
        confidence = data.get("confidence")
        if confidence is None or confidence < min_confidence:
            violations.append({
                "field": "confidence",
                "issue": "below_min_confidence",
                "detail": (
                    f"Confidence {confidence} is below min_confidence "
                    f"{min_confidence} for filing type '{filing_type}'."
                ),
            })

    if spec.get("requires_source_id") and not data.get("source_id"):
        violations.append({
            "field": "source_id",
            "issue": "source_id_missing",
            "detail": (
                f"Filing type '{filing_type}' requires a source_id; none provided."
            ),
        })

    return violations


def build_filing_suggestions(policy: dict, counts: dict) -> list:
    """Return advisory filing suggestion objects based on policy and lifecycle counts.

    Each suggestion has:
      - type: one of "answer", "analysis", "synthesis"
      - reason: human-readable string grounded in when_to_file / provenance_expectations
      - confidence_band: "high" or "review"
      - recommended_action: "file", "review", or "skip"

    The suggestions are advisory only; enforcement_mode is never changed.
    """
    suggestions = []
    bands = policy.get("confidence_bands", {}) or {}
    high_threshold = bands.get("high", 0.8)
    review_threshold = bands.get("review", 0.55)
    when_to_file = policy.get("when_to_file", []) or []
    prov = policy.get("provenance_expectations", {}) or {}

    active = counts.get("active_records", 0)
    hot = counts.get("hot_records", 0)
    open_pendencias = counts.get("open_pendencias", 0)

    # Suggest filing a durable answer when there are active records worth capturing
    if active > 0 and when_to_file:
        reason = when_to_file[0]  # "Captures durable insight…"
        suggestions.append({
            "type": "answer",
            "reason": reason,
            "confidence_band": "high",
            "recommended_action": "file",
        })

    # Suggest filing an analysis when there are HOT records that likely have source-linked depth
    if hot > 0:
        prov_analysis = prov.get(
            "analysis",
            "Must carry source_id; reference the summary, not restate it.",
        )
        suggestions.append({
            "type": "analysis",
            "reason": prov_analysis,
            "confidence_band": "review",
            "recommended_action": "review",
        })

    # Suggest filing a synthesis when open pendencias exist (cross-record integration value)
    if open_pendencias > 0 and len(when_to_file) >= 2:
        reason = when_to_file[1]  # "Distills knowledge from multiple records…"
        suggestions.append({
            "type": "synthesis",
            "reason": reason,
            "confidence_band": "review",
            "recommended_action": "review",
        })

    return suggestions


def cmd_filing_policy(args: argparse.Namespace, *, emit, load_config=None) -> None:
    """Readonly CLI: emit the resolved filing policy.

    Policy is advisory. `kb file` does not gate on this policy.
    """
    loader = load_config or _load_config
    policy = get_filing_policy(loader())

    if getattr(args, "json", False):
        emit(policy, True)
        return

    lines = [
        f"Filing policy (enforcement_mode: {policy.get('enforcement_mode', 'advisory')})",
    ]
    if policy.get("resolved_profile"):
        lines.append(f"  profile: {policy['resolved_profile']}")
    bands = policy.get("confidence_bands", {}) or {}
    lines.append(
        f"  confidence bands: high>={bands.get('high')} review>={bands.get('review')}"
    )
    lines.append("  filing types:")
    for ftype, spec in (policy.get("filing_types", {}) or {}).items():
        lines.append(
            f"    - {ftype}: categories={spec.get('allowed_categories')} "
            f"requires_source_id={spec.get('requires_source_id')} "
            f"min_confidence={spec.get('min_confidence')}"
        )
    for label, key in (("when to file", "when_to_file"), ("when NOT to file", "when_not_to_file")):
        items = policy.get(key, []) or []
        if items:
            lines.append(f"  {label}:")
            for item in items:
                lines.append(f"    - {item}")
    prov = policy.get("provenance_expectations", {}) or {}
    if prov:
        lines.append("  provenance expectations:")
        for ftype, expectation in prov.items():
            lines.append(f"    - {ftype}: {expectation}")
    lines.append("Note: advisory. `kb file` does not gate on this policy.")
    emit({"__plain__": True, "text": "\n".join(lines)}, False)
