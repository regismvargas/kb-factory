from __future__ import annotations


CATEGORIES = {"DECISAO", "PREMISSA", "FATO", "PENDENCIA", "APRENDIZADO"}
STATUSES = {"ATIVO", "SUPERSEDIDO", "RESOLVIDO"}
TIERS = {"HOT", "WARM", "COLD"}

# run_wiki_sync is a no-op while the wiki is off, so the events that change
# records or close a session keep an enabled wiki current without a manual
# `wiki-sync`. session_start stays read-only.
LIFECYCLE_DEFAULTS = {
    "events": {
        "session_start": {
            "run_audit": True,
            "apply_demotions": False,
            "refresh_exports": False,
            "run_wiki_check": True,
            "run_wiki_lint": False,
            "run_wiki_sync": False,
        },
        "source_ingest": {
            "run_audit": False,
            "apply_demotions": False,
            "refresh_exports": True,
            "run_wiki_check": True,
            "run_wiki_lint": False,
            "run_wiki_sync": True,
        },
        "record_filed": {
            "run_audit": False,
            "apply_demotions": False,
            "refresh_exports": True,
            "run_wiki_check": True,
            "run_wiki_lint": False,
            "run_wiki_sync": True,
        },
        "session_end": {
            "run_audit": True,
            "apply_demotions": False,
            "apply_cold_demotions": False,
            "prune_snapshots": False,
            "refresh_exports": True,
            "run_wiki_check": False,
            "run_wiki_lint": True,
            "run_wiki_sync": True,
        },
        "scheduled_maintenance": {
            "run_audit": True,
            "apply_demotions": True,
            "apply_cold_demotions": False,
            "prune_snapshots": False,
            "refresh_exports": True,
            "run_wiki_check": True,
            "run_wiki_lint": True,
            "run_wiki_sync": True,
        },
    }
}
