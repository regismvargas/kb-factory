# Manual Do Usuário KB/Wiki vNext

## Purpose / Propósito

Usar o KB/Wiki vNext para iniciar uma sessão de memória fina, consultar memória do projeto, preparar propostas governadas e revisar drafts de wiki sem transformar `.kb-next/` na fonte canônica.

## Audience / Público

Usuários de projeto que recebem o ZIP de plugin ou o bundle stand-alone de um maintainer.

## Prerequisites / Pré-requisitos

- Python disponível como `python`.
- Workspace com pasta `.kb/` criada pelo template clássico do bundle ou por um workspace KB Factory existente.
- Um canal instalado: plugin Codex, plugin Claude Code, plugin Claude Cowork ou bundle stand-alone.

## Passos

Escolha o pacote certo para o cliente:

- Codex: `kb-wiki-vnext-plugin-0.3.0.zip`
- Claude Code: `kb-wiki-vnext-claude-plugin-0.3.0.zip`
- Claude Cowork: `kb-wiki-vnext-cowork-plugin-0.3.0.zip`
- Stand-alone: `kb-wiki-vnext-0.3.0-standalone.zip`

Release, KB Lifecycle, vNext e runtime incluído usam `0.3.0`; Session Gate
permanece `0.2.7`. Marketplace e catálogo não têm linha própria de versão.
Registre versões dos manifestos e hashes dos artefatos na instalação ou upgrade.

Em instalação por plugin, use `existing-project-activate-vnext` para resolver o
engine incluído e fazer bootstrap do workspace. O fluxo equivalente no shell é:

```powershell
python <installed-plugin-runtime> --project-root . bootstrap --json
python .\.kb-next\runtime\kb_next.py session-start --json
python .\.kb-next\runtime\kb_next.py lookup --facet status --query "status atual" --json
```

Resolva `<installed-plugin-runtime>` em `${CLAUDE_PLUGIN_ROOT}/runtime/kb_next.py`
ou no caminho do plugin instalado no Codex, Cowork ou Claude. Não presuma que o
path de autoria KB Factory existe em projeto consumer.

No layout do repositório:

```powershell
python core\versions\kb-wiki-vnext\runtime\kb_next.py session-start --json
python core\versions\kb-wiki-vnext\runtime\kb_next.py lookup --facet status --query "status atual" --json
```

No layout do bundle stand-alone:

```powershell
python runtime\kb_next.py session-start --json
python runtime\kb_next.py lookup --facet status --query "status atual" --json
```

Para manter um runtime persistente no workspace, rode uma vez o engine
stand-alone com `--project-root <workspace> bootstrap --json` e use depois
`<workspace>/.kb-next/runtime/kb_next.py` nas sessões normais.

Use `proposal-apply` apenas quando uma proposta preparada for aprovada de propósito. Não edite `.kb/kb.db` diretamente.

Os workflows instalados usam nomes lógicos explícitos. Claude Code invoca
`/kb-wiki-vnext:vnext-session-start`; Codex usa o skill embutido
`kb-wiki-vnext` como superfície principal; Cowork usa a ação namespaced
realmente exposta pela UI ou o skill em linguagem natural. As famílias lógicas
`existing-project-*` e `new-project-*` cobrem workspaces legados e novos. Não
presuma que um slash command nu funciona em todos os clientes.

Para exemplos de runtime e padrões seguros de conversa, use o [guia de uso detalhado](usage-guide.md).

## Verification / Verificação

O runtime `session-start` deve informar o modo ativo e apontar para
`.kb-next/memory/NOW.md`. O basename lógico é `vnext-session-start`; a
invocação depende do cliente. `lookup`
pode retornar zero registros em um workspace novo e anexa evidência operacional
a `.kb-next/operations.jsonl`, mas não pode alterar `.kb/` canônica nem publicar
`.kb/wiki/live`.

## Troubleshooting / Solução De Problemas

Se o runtime não encontrar `.kb/kb.py`, copie `classic-template/.kb/` do bundle
stand-alone para um projeto novo como `.kb/`; nunca sobrescreva `.kb/` existente.
Se `.kb-next/runtime/kb_next.py` estiver ausente, faça bootstrap a partir do
engine do plugin instalado ou do stand-alone. No Cowork, use a ação namespaced
exposta pela UI do plugin, invoque o skill em linguagem natural ou rode o
fallback do runtime.

## Related / Relacionados

- [Guia de uso detalhado](usage-guide.md)
- [Instalação para admins](admin-installation.md)
- [Referência de comandos](command-reference.md)
- [Upgrade e rollback](upgrade-rollback.md)
- [Arquitetura](architecture.md)
