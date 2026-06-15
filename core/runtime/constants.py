from __future__ import annotations


CATEGORIES = {"DECISAO", "PREMISSA", "FATO", "PENDENCIA", "APRENDIZADO"}
STATUSES = {"ATIVO", "SUPERSEDIDO", "RESOLVIDO"}
TIERS = {"HOT", "WARM", "COLD"}

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
            "run_wiki_sync": False,
        },
        "record_filed": {
            "run_audit": False,
            "apply_demotions": False,
            "refresh_exports": True,
            "run_wiki_check": True,
            "run_wiki_lint": False,
            "run_wiki_sync": False,
        },
        "session_end": {
            "run_audit": True,
            "apply_demotions": False,
            "apply_cold_demotions": False,
            "prune_snapshots": False,
            "refresh_exports": True,
            "run_wiki_check": False,
            "run_wiki_lint": True,
            "run_wiki_sync": False,
        },
        "scheduled_maintenance": {
            "run_audit": True,
            "apply_demotions": True,
            "apply_cold_demotions": False,
            "prune_snapshots": False,
            "refresh_exports": True,
            "run_wiki_check": True,
            "run_wiki_lint": True,
            "run_wiki_sync": False,
        },
    }
}
