# Instalação E Distribuição Admin KB/Wiki vNext

## Purpose / Propósito

Dar aos admins um processo repetível para distribuir KB/Wiki vNext a projetos controlados sem transformar histórico de workbench no onboarding principal.

## Audience / Público

Admins de workspace, leads técnicos e maintainers que instalam o pacote para outras pessoas.

## Prerequisites / Pré-requisitos

- Artefato de release limpo, gerado a partir deste repositório.
- Acesso ao cliente de destino: Codex, Claude Code, Claude Cowork ou workspace com Python.
- Alinhamento com o dono do workspace de que `.kb/` segue canônico e `.kb-next/` é a camada vNext.
- A identidade de release registra separadamente produto `0.2.0-rc.2`, KB
  Lifecycle `0.2.3`, plugin `0.1.9`, runtime incluído `0.1.7`, Session Gate
  `0.2.7` e marketplace `0.3.8`.

## Passos

Gere todos os distribuíveis KB afetados e o bundle stand-alone:

```powershell
python tools\build_agent_packages.py --scope kb
python tools\build_vnext_standalone.py --version 0.2.0-rc.2
```

Valide antes de compartilhar:

```powershell
python tools\validate_vnext_product.py --bundle dist\vnext\kb-wiki-vnext-0.2.0-rc.2-standalone.zip
```

Distribua apenas o artefato correspondente:

- Usuários Codex recebem o ZIP de plugin Codex.
- Usuários Claude Code recebem o ZIP de plugin Claude Code.
- Usuários Claude Cowork recebem o ZIP Cowork e instruções explícitas de
  startup manual com `vnext-session-start`.
- Usuários Session Gate recebem o artefato `session-gate-*-0.2.7.zip`
  correspondente e usam `gate-session-start` / `gate-session-end`.
- Admins que criam workspace novo recebem o bundle stand-alone.

O Codex CLI não possui comando de gerenciamento de plugins. No app Codex, use
as configurações de Plugins com o marketplace público
`regismvargas/kb-factory` ou carregue
`kb-wiki-vnext-plugin-0.1.9.zip` quando a instalação por arquivo estiver
disponível. Reiniciar sozinho não busca uma versão mais nova do marketplace.

Todo ZIP de plugin vNext deve conter `runtime/kb_next.py` na raiz do arquivo.
Não distribua artefato que contenha apenas comandos referindo-se ao engine
incluído, mas omita esse arquivo.

Em workspace consumer por plugin, resolva o engine em
`${CLAUDE_PLUGIN_ROOT}/runtime/kb_next.py` ou no path do plugin instalado no
cliente e rode:

```powershell
python <installed-plugin-runtime> --project-root <workspace> bootstrap --json
```

Na distribuição stand-alone, use `runtime/kb_next.py` do bundle descompactado
como `<installed-plugin-runtime>`. Nunca sobrescreva `.kb/` existente no
workspace com `classic-template/.kb/`.

## Verification / Verificação

Confirme que o arquivo contém `runtime/kb_next.py`; o bootstrap informa a versão
esperada do runtime e `source_sha256` igual a `installed_sha256`; o destinatário
consegue invocar a superfície vNext específica do cliente, ler
`.kb-next/memory/NOW.md` e executar o runtime instalado com
`lookup --facet status`. As operações de início e lookup do runtime podem anexar
`.kb-next/operations.jsonl`, mas instalação e verificação
não podem alterar `.kb/` canônica nem publicar `.kb/wiki/live`. Para Session
Gate, confirme que a superfície de startup específica do cliente detecta `.kb-next/` antes de cair no
`.kb/` clássico.

## Troubleshooting / Solução De Problemas

Se o ZIP errado for instalado, remova o pacote pelo cliente usado e instale o
pacote correto. Se um ZIP de plugin não contiver `runtime/kb_next.py`, ou se o
bundle stand-alone estiver sem docs ou template clássico, bloqueie a
distribuição e gere o ZIP novamente pelo build script.

## Related / Relacionados

- [Manual do usuário](user-manual.md)
- [Referência de comandos](command-reference.md)
- [Release para maintainers](maintainer-release.md)
- [Troubleshooting](troubleshooting.md)
