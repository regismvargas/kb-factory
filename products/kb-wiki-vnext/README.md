# KB/Wiki vNext Product

KB/Wiki vNext is packaged here as a controlled, stand-alone release candidate for team/admin distribution.

Version: `0.3.0`
Current audited plugin component line: `0.3.0`

Bundled runtime engine: `0.3.0`
KB Lifecycle companion line: `0.3.0`
Session Gate companion line: `0.2.7`
Marketplace version authority: none; plugin manifests are authoritative

## Start Here

English:

- [User manual](docs/en/user-manual.md)
- [Detailed usage guide](docs/en/usage-guide.md)
- [Command reference](docs/en/command-reference.md)
- [Admin installation and distribution](docs/en/admin-installation.md)
- [Upgrade and rollback](docs/en/upgrade-rollback.md)
- [Architecture and operating model](docs/en/architecture.md)
- [Maintainer and release manual](docs/en/maintainer-release.md)
- [Troubleshooting](docs/en/troubleshooting.md)

Português:

- [Manual do usuário](docs/pt-BR/user-manual.md)
- [Guia de uso detalhado](docs/pt-BR/usage-guide.md)
- [Referência de comandos](docs/pt-BR/command-reference.md)
- [Instalação e distribuição para admins](docs/pt-BR/admin-installation.md)
- [Upgrade e rollback](docs/pt-BR/upgrade-rollback.md)
- [Arquitetura e modelo operacional](docs/pt-BR/architecture.md)
- [Manual de manutenção e release](docs/pt-BR/maintainer-release.md)
- [Troubleshooting](docs/pt-BR/troubleshooting.md)

## Maintainer Commands

```powershell
python tools\build_vnext_standalone.py --version 0.3.0
python tools\validate_vnext_product.py --bundle dist\vnext\kb-wiki-vnext-0.3.0-standalone.zip
```

## Authority Boundary

`.kb/` remains canonical. `.kb-next/` is the vNext operational, proposal, evidence, draft, and materialization layer. The approved bridge back to canonical memory is `proposal-apply` through `.kb/kb.py`; product tooling must not mutate `.kb/kb.db` directly or publish into `.kb/wiki/live`.

## Related

- [Product manifest](product.json)
- [Root install guide](../../docs/installation.md)
- [Standalone builder](../../tools/build_vnext_standalone.py)
- [Product validator](../../tools/validate_vnext_product.py)
