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
| `vnext-session-end` | sessão vNext geral | Codex, Claude Code, Claude Cowork | resumir evidência vNext | sem escrita canônica por padrão |
| `existing-project-diagnose` | existente/legado | Codex, Claude Code, Claude Cowork | inspecionar `.kb/`, `.kb-next/`, runtime e `NOW.md` | sem escrita canônica; anexa operações se rodar `session-start` |
| `existing-project-activate-vnext` | existente/legado | Codex, Claude Code, Claude Cowork | `activation-wizard --mode short --choice kb-alone` por padrão | escreve `.kb-next/`, não `.kb/` |
| `existing-project-configure-vnext` | existente/legado | Codex, Claude Code, Claude Cowork | `activation-wizard` curto ou guiado | escreve `.kb-next/`, não `.kb/` |
| `existing-project-verify-install` | existente/legado | Codex, Claude Code, Claude Cowork | `session-start` mais `lookup` determinístico | sem escrita canônica; append em `.kb-next/operations.jsonl` |
| `existing-project-upgrade-vnext` | existente/legado | Codex, Claude Code, Claude Cowork | bootstrap pelo artefato substituto e conferir a nova versão | pacote/runtime do workspace mais evidência operacional; sem escrita canônica |
| `existing-project-rollback-vnext` | existente/legado | Codex, Claude Code, Claude Cowork | bootstrap pelo artefato restaurado e conferir a versão anterior | pacote/runtime do workspace mais evidência operacional; sem escrita canônica |
| `new-project-wizard` | projeto novo | Codex, Claude Code, Claude Cowork | semear template clássico se necessário e escolher modo | cria `.kb/` e `.kb-next/` quando ausentes |
| `new-project-init-kb-alone` | projeto novo | Codex, Claude Code, Claude Cowork | `activation-wizard --mode short --choice kb-alone` | cria/configura `.kb-next/` |
| `new-project-init-kb-wiki` | projeto novo | Codex, Claude Code, Claude Cowork | `activation-wizard --mode short --choice kb-wiki` | cria/configura `.kb-next/`; sem publicação live |
| `new-project-verify-install` | projeto novo | Codex, Claude Code, Claude Cowork | `session-start` mais `lookup` determinístico | sem escrita canônica; append em `.kb-next/operations.jsonl` |
| `gate-session-start` | Session Gate | Codex, Claude Code, Claude Cowork | detectar `.kb-next/`, `.kb/`, CASE; rotear vNext primeiro | sem escrita canônica; rota vNext faz append em `.kb-next/operations.jsonl` |
| `gate-session-end` | Session Gate | Codex, Claude Code, Claude Cowork | detectar sistemas e resumir closeout | sem escrita canônica por padrão |

Comando apenas de runtime:

| Subcomando | Propósito | Comportamento de mutação |
|---|---|---|
| `bootstrap` | instalar atomicamente o runtime do artefato em execução em `<project>/.kb-next/runtime/kb_next.py` | substitui drift de bytes, reporta SHA-256 de origem/instalado e rejeita alvos inseguros; `action: self` não prova upgrade |

`.kb/` continua sendo memória durável canônica. `.kb-next/` continua sendo
estado governado de proposta, evidência, draft, materialização e operações.
