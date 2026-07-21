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
python tools\build_vnext_standalone.py --version 0.3.0
```

Validação:

```powershell
python tools\validate_vnext_product.py --bundle dist\vnext\kb-wiki-vnext-0.3.0-standalone.zip
python tools\validate_kb_wiki_vnext_spec_pack.py
python -m pytest -p no:cacheprovider --basetemp=.pytest_tmp_vnext_compliance tests\test_kb_wiki_vnext_runtime.py tests\test_kb_wiki_vnext_semantic_runtime.py tests\test_kb_wiki_vnext_spec_pack.py tests\test_build_agent_packages.py tests\test_vnext_product.py -q
```

Auditoria de hashes:

```powershell
Get-FileHash dist\vnext\kb-wiki-vnext-0.3.0-standalone.zip -Algorithm SHA256
Get-ChildItem dist\agent-packages\*vnext*.zip,dist\agent-packages\session-gate-*.zip | Get-FileHash -Algorithm SHA256
```

Planejamento de limpeza:

```powershell
python tools\cleanup_vnext_workbench.py --dry-run
```

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
