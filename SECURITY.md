# Security Policy

## Reporting a vulnerability

Please do **not** open a public issue for security problems.

Report vulnerabilities privately through GitHub's **"Report a vulnerability"**
feature (Security → Advisories) on this repository. If that is unavailable, open
a minimal public issue asking a maintainer to open a private channel — without
disclosing details.

We aim to acknowledge a report within a few business days and to keep you
informed as we investigate and prepare a fix. Please give us reasonable time to
remediate before any public disclosure.

## Supported versions

KB Factory is pre-1.0. Security fixes are applied to the latest released version
and to `main`. Older versions are not maintained.

| Version | Supported |
|---|---|
| latest release / `main` | ✅ |
| older | ❌ |

## Scope and threat model

KB Factory is **local-first and dependency-free**: the runtime is the Python
standard library plus SQLite, with no network service and no external service
calls. This shapes what "security" means here:

- **No server / no network listener.** There is no remote attack surface in the
  core runtime. The knowledge base is a local SQLite file the operator controls.
- **The data is the asset.** Treat `.kb/kb.db` and generated exports as you would
  any project file: they may contain whatever you choose to record. Do not commit
  a real `kb.db` to a public repository.
- **Ingested sources are untrusted input.** When you ingest external sources into
  the KB, treat their content as untrusted (e.g., prompt-injection risk when an
  agent later reads them). The KB stores and attributes content; it does not vet
  it. Verify sensitive facts against the source, per the KB's own discipline.
- **Out of scope:** issues that require an already-compromised local machine, or
  that depend on third-party tools layered on top of KB Factory.

If you are unsure whether something is in scope, report it privately and we will
help triage.
