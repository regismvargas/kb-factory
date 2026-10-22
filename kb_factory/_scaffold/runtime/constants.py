from __future__ import annotations


CATEGORIES = {"DECISAO", "PREMISSA", "FATO", "PENDENCIA", "APRENDIZADO"}
STATUSES = {"ATIVO", "SUPERSEDIDO", "RESOLVIDO"}
TIERS = {"HOT", "WARM", "COLD"}

# Records the KB Factory template seeded before kb-lifecycle 0.2.6. They
# describe the KB, not the project, so the derived surfaces (NOW, HOT, INDEX,
# topics, packs, wiki candidates and wiki signals) leave them out. They stay in
# kb.db and in search. A match needs the template title and a bootstrap
# source, so a record the project rewrote is never hidden.
BOOTSTRAP_SEED_SOURCES = ("project-bootstrap", "kb-factory-blueprint")
BOOTSTRAP_SEED_TITLES = (
    "KB enabled as the project's operating memory",
    "Initial project scope remains valid until first KB review",
    "The primary runtime is local-first",
    "Review HOT criteria after first real sessions",
    "Search before assuming reduces context drift",
)


def _sql_literals(values: tuple[str, ...]) -> str:
    return ", ".join("'" + value.replace("'", "''") + "'" for value in values)


# SQL condition on the `records` table: true for every record except those seeds.
NOT_BOOTSTRAP_SEED = (
    f"NOT (COALESCE(source, '') IN ({_sql_literals(BOOTSTRAP_SEED_SOURCES)}) "
    f"AND title IN ({_sql_literals(BOOTSTRAP_SEED_TITLES)}))"
)

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
