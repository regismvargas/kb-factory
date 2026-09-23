# Referência De Comandos KB/Wiki vNext

Use nomes explícitos de comandos. Não use aliases genéricos
`/session-start` ou `/session-end` para os pacotes vNext ou Session Gate.

Paths de runtime são resolvidos separadamente dos nomes de comandos do plugin.
Em sessões normais no shell, use `./.kb-next/runtime/kb_next.py`; se estiver
ausente, resolva o `runtime/kb_next.py` incluído no plugin e rode `bootstrap`.
Use o path de autoria `core/versions/...` apenas dentro do KB Factory.

A tabela abaixo usa **basenames lógicos**, não uma invocação literal única para
todos os clientes:

| Cliente | Invocação de startup |
|---|---|
| Claude Code | `/kb-wiki-vnext:vnext-session-start` |
| Codex | invoque o skill embutido `kb-wiki-vnext` em linguagem natural; use o fallback de runtime quando necessário |
| Claude Cowork | use a ação namespaced exposta pela UI do plugin instalado, ou invoque o skill em linguagem natural; use o fallback de runtime quando comandos não forem expostos |

Não prometa slash command nu como `/vnext-session-start` em todos os clientes.
Session Gate segue a mesma distinção com o basename lógico
`gate-session-start`.

| Comando | Tipo de projeto | Plataformas | Runtime ou instrução | Comportamento de mutação |
|---|---|---|---|---|
| `vnext-session-start` | sessão vNext geral | Codex, Claude Code, Claude Cowork | `python ./.kb-next/runtime/kb_next.py session-start --json` depois do bootstrap | sem escrita canônica; append em `.kb-next/operations.jsonl` |
| `vnext-session-end` | sessão vNext geral | Codex, Claude Code, Claude Cowork | resumir evidência vNext; rodar `python .kb/kb.py lifecycle session-end` e, com KB + Wiki, o `wiki-draft-status` do runtime | o session-end clássico atualiza exports e o wiki habilitado; sem escrita canônica de registros |
| `vnext-wiki-drafts` | sessão KB + Wiki | Codex, Claude Code, Claude Cowork | `wiki-draft-status` e, por tópico, `wiki-synthesis-plan` com julgamento do agente e `wiki-draft-review --materialize` | grava drafts, manifests e páginas em `.kb-next/wiki/`; sem escrita canônica |
| `existing-project-diagnose` | existente/legado | Codex, Claude Code, Claude Cowork | inspecionar `.kb/`, `.kb-next/`, runtime e `NOW.md` | sem escrita canônica; anexa operações se rodar `session-start` |
| `existing-project-activate-vnext` | existente/legado | Codex, Claude Code, Claude Cowork | `activation-wizard --mode short --choice kb-alone` por padrão | escreve `.kb-next/`; com `kb-wiki` também liga as chaves do wiki clássico em `.kb/kb.config.json` e sincroniza `.kb/wiki/live` |
| `existing-project-configure-vnext` | existente/legado | Codex, Claude Code, Claude Cowork | `activation-wizard` curto ou guiado (faz merge da config existente) | escreve `.kb-next/`; `kb-wiki` liga e sincroniza o wiki clássico; `kb-alone` o mantém, exceto com `--disable-classic-wiki` |
| `existing-project-verify-install` | existente/legado | Codex, Claude Code, Claude Cowork | `session-start` mais `lookup` determinístico | sem escrita canônica; append em `.kb-next/operations.jsonl` |
| `existing-project-upgrade-vnext` | existente/legado | Codex, Claude Code, Claude Cowork | bootstrap pelo artefato substituto, `upgrade-classic`, reaplicar o modo registrado e verificar | runtimes do workspace, arquivos do motor clássico e chaves do wiki clássico; sem escrita canônica de registros |
| `existing-project-rollback-vnext` | existente/legado | Codex, Claude Code, Claude Cowork | bootstrap pelo artefato restaurado e conferir a versão anterior | pacote/runtime do workspace mais evidência operacional; sem escrita canônica |
| `new-project-wizard` | projeto novo | Codex, Claude Code, Claude Cowork | pedir título, slug e domínios e escolher o modo de init | cria `.kb/` (via `install-classic`) e `.kb-next/` quando ausentes |
| `new-project-init-kb-alone` | projeto novo | Codex, Claude Code, Claude Cowork | `install-classic`, `bootstrap`, `activation-wizard --mode short --choice kb-alone` | cria `.kb/` quando ausente e configura `.kb-next/` |
| `new-project-init-kb-wiki` | projeto novo | Codex, Claude Code, Claude Cowork | `install-classic`, `bootstrap`, `activation-wizard --mode short --choice kb-wiki` | cria `.kb/` quando ausente e `.kb-next/`; liga o wiki clássico e publica `.kb/wiki/live`; drafts vNext nunca são copiados para lá |
| `new-project-verify-install` | projeto novo | Codex, Claude Code, Claude Cowork | `session-start` mais `lookup` determinístico | sem escrita canônica; append em `.kb-next/operations.jsonl` |
| `gate-session-start` | Session Gate | Codex, Claude Code, Claude Cowork | detectar `.kb-next/` e `.kb/`; rotear vNext primeiro | sem escrita canônica; rota vNext faz append em `.kb-next/operations.jsonl` |
| `gate-session-end` | Session Gate | Codex, Claude Code, Claude Cowork | detectar sistemas e resumir closeout | sem escrita canônica por padrão |

Comandos apenas de runtime:

| Subcomando | Propósito | Comportamento de mutação |
|---|---|---|
| `bootstrap` | instalar atomicamente o runtime do artefato em execução em `<project>/.kb-next/runtime/kb_next.py` | substitui drift de bytes, reporta SHA-256 de origem/instalado e rejeita alvos inseguros; `action: self` não prova upgrade |
| `install-classic` | copiar o scaffold clássico (plugin kb-lifecycle, bundle stand-alone, repo de autoria ou `--template`) para `.kb/` e rodar `init --name --slug --domains` | cria `.kb/`; recusa `.kb/` existente ou não vazio |
| `upgrade-classic` | atualizar só `.kb/kb.py` e `.kb/runtime/*.py` a partir do scaffold encontrado | só arquivos do motor; nunca `kb.db`, dados ou `kb.config.json` |
| `wiki-draft-status` | listar tópicos do wiki que precisam de síntese, revisão ou atualização | somente leitura |
| `session-hint` | texto do hook SessionStart para workspaces vNext | somente leitura; não imprime nada fora de workspaces vNext |

`.kb/` continua sendo memória durável canônica. `.kb-next/` continua sendo
estado governado de proposta, evidência, draft, materialização e operações.
