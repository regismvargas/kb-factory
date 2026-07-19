# Manual De Manutenção E Release KB/Wiki vNext

## Purpose / Propósito

Definir como maintainers reconstróem, validam, auditam e liberam o pacote RC do vNext.

## Audience / Público

Maintainers responsáveis por packaging, QA e distribuição controlada.

## Prerequisites / Pré-requisitos

- Trabalhar em branch com tag de baseline reversível.
- Manter arquivos sujos não relacionados fora do commit de release.
- Não publicar saída gerada em `.kb/wiki/live`.

## Passos

Build:

```powershell
python tools\build_agent_packages.py --scope vnext
python tools\build_vnext_standalone.py --version 0.2.0-rc.2
```

Validação:

```powershell
python tools\validate_vnext_product.py --json --bundle dist\vnext\kb-wiki-vnext-0.2.0-rc.2-standalone.zip
python tools\sync_vnext_runtime.py --check
python -m pytest -p no:cacheprovider tests -q
```

Auditoria de hashes:

```powershell
Get-FileHash dist\vnext\kb-wiki-vnext-0.2.0-rc.2-standalone.zip -Algorithm SHA256
Get-ChildItem dist\agent-packages\*vnext*.zip,dist\agent-packages\session-gate-*.zip | Get-FileHash -Algorithm SHA256
```

Confirme que `git status --short` contém apenas as mudanças públicas pretendidas.

## Verification / Verificação

O release é aceitável quando os validadores passam, docs obrigatórias existem
em inglês e português, ZIPs de plugin incluem `runtime/kb_next.py`, invocações
por cliente não presumem slash command universal, hashes e todas as versões de
componentes estão registrados, e o ZIP stand-alone exclui `.kb/kb.db`,
`.kb/wiki/live`, caches, worktrees e `state/runs`.

## Troubleshooting / Solução De Problemas

Se um artefato obrigatório ou runtime incluído estiver ausente, gere novamente
a partir da fonte em vez de editar o ZIP manualmente. Se docs e manifesto
divergirem, atualize ambos no mesmo change. Se arquivos genéricos
`session-start` / `session-end` reaparecerem nos pacotes vNext ou Session Gate,
bloqueie o release. Não substitua bytes já publicados sob a mesma versão sem
uma decisão explícita de imutabilidade.

## Related / Relacionados

- [Arquitetura](architecture.md)
- [Referência de comandos](command-reference.md)
- [Upgrade e rollback](upgrade-rollback.md)
- [Instalação para admins](admin-installation.md)
