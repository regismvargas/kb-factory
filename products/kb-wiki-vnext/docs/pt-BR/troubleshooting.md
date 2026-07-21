# Troubleshooting KB/Wiki vNext

## Purpose / Propósito

Oferecer diagnóstico inicial para problemas de instalação, runtime, packaging e rollback.

## Audience / Público

Usuários, admins e maintainers que dão suporte a deployments controlados.

## Prerequisites / Pré-requisitos

- Saber qual artefato foi instalado.
- Manter o workspace com falha sem mudanças até capturar diagnóstico básico.
- Não rodar comandos destrutivos de limpeza durante diagnóstico.

## Checks Comuns

Resolva o runtime nesta ordem: workspace `.kb-next/runtime/kb_next.py`, plugin
ativo `${CLAUDE_PLUGIN_ROOT}/runtime/kb_next.py`, path do plugin instalado no
cliente, `runtime/kb_next.py` stand-alone e, por último, path de autoria KB
Factory. Confirme o help:

```powershell
python <resolved-runtime-path> --help
```

Se o runtime do workspace estiver ausente, faça bootstrap a partir do plugin ou
artefato stand-alone e confirme o startup:

```powershell
python <artifact-runtime-path> --project-root . bootstrap --json
python .\.kb-next\runtime\kb_next.py session-start --json
```

Confirmar pacote de produto:

```powershell
python tools\validate_vnext_product.py --bundle dist\vnext\kb-wiki-vnext-0.3.0-standalone.zip
```

Para exemplos de runtime e prompts seguros de conversa, veja o [guia de uso detalhado](usage-guide.md).

## Verification / Verificação

Um workspace saudável roda a superfície de startup do cliente ou o
`session-start` do runtime, lê `.kb-next/memory/NOW.md` e conclui `lookup` ou
`semantic-hygiene` padrão sem mudar `.kb/kb.db`. `lookup` e `session-start`
anexam evidência operacional; `semantic-hygiene` padrão não escreve. O Session
Gate deve rotear `.kb-next/` antes do `.kb/` clássico.

## Troubleshooting / Solução De Problemas

Se `.kb/kb.py` estiver ausente em projeto novo, faça bootstrap com
`classic-template/.kb/`; nunca sobrescreva `.kb/` existente. Se a instalação do
plugin falhar, confira se o pacote corresponde à plataforma, contém
`runtime/kb_next.py` e omite arquivos genéricos `session-start` / `session-end`.
Se o bootstrap retornar `action: self` durante upgrade ou rollback, resolva o
artefato substituto ou restaurado, não o runtime atual do workspace. Se
`semantic-hygiene` reportar problemas, trate como findings de revisão até
existir autorização separada para criar propostas. Se algum comando alterar
memória canônica inesperadamente, pare e compare o backup.

Para falhas de grafo, rode primeiro `graph verify --json`. Exit `1` significa
findings estruturais, não crash do runtime. Em KB schema v5,
`TYPED_EDGE_CAPABILITY_UNAVAILABLE` é warning esperado. Exit `2` significa
erro de uso ou ambiente. Se qualquer leitura vNext mudar o hash do DB ou da
árvore `.kb-next`, pare: o contrato read-only foi violado. Não aplique a saída
de `source-backfill` automaticamente.

## Related / Relacionados

- [Guia de uso detalhado](usage-guide.md)
- [Manual do usuário](user-manual.md)
- [Referência de comandos](command-reference.md)
- [Upgrade e rollback](upgrade-rollback.md)
- [Release para maintainers](maintainer-release.md)
