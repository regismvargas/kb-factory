# Arquitetura E Modelo Operacional KB/Wiki vNext

## Purpose / Propósito

Explicar o que o produto contém, como cada plataforma usa o pacote e onde começa e termina a autoridade do vNext.

## Audience / Público

Admins, desenvolvedores, revisores e maintainers que avaliam o pacote RC.

## Prerequisites / Pré-requisitos

- Familiaridade básica com workspaces KB Factory.
- Entendimento de que este RC é productizado dentro do repositório atual, sem separação para outro repo nesta rodada.

## Modelo Operacional

`.kb/` é a memória canônica. `.kb-next/` é evidência, proposta, draft, materialização e memória operacional dos fluxos vNext. O runtime vNext pode ler `.kb/` por superfícies suportadas, mas mutação canônica deve passar por `proposal-apply`, que delega para `.kb/kb.py`.

Mapa de plataforma:

| Plataforma | Artefato | Estrutura interna | Capacidades principais |
| --- | --- | --- | --- |
| Codex | `kb-wiki-vnext-plugin-0.1.9.zip` | `.codex-plugin`, skills, comandos e runtime `0.1.7` | `vnext-session-start`, comandos de setup, lookup, compliance preflight, propostas |
| Claude Code | `kb-wiki-vnext-claude-plugin-0.1.9.zip` | manifesto Claude, skills, comandos/hooks e runtime `0.1.7` | fluxos guiados de memória e comandos explícitos |
| Claude Cowork | `kb-wiki-vnext-cowork-plugin-0.1.9.zip` | pacote Cowork, runtime `0.1.7` e orientação de sessão manual | `vnext-session-start` manual, comandos de setup, sem depender de hooks automáticos |
| Session Gate | `session-gate-*-0.2.7.zip` | detector de plugin mais comandos `gate-session-*` | rotear `.kb-next/` primeiro, depois `.kb/` clássico e CASE quando presentes |
| Stand-alone | `kb-wiki-vnext-0.2.0-rc.2-standalone.zip` | runtime, template clássico, plugin source, docs, tools | bootstrap e distribuição controlada por admin |

Plugin instala capacidades no cliente. Skills descrevem comportamento do agente. Commands expõem workflows chamáveis. Hooks são conveniências específicas de plataforma e não são assumidos no Cowork.

Os nomes na coluna de capacidades são basenames lógicos. Claude Code prefixa
comandos do plugin com `/kb-wiki-vnext:`; Codex usa o skill embutido como
superfície principal; Cowork segue as ações expostas pela UI do plugin instalado.

As linhas de versão são identidades independentes de componentes:

| Componente | Versão |
|---|---|
| Release candidate do produto | `0.2.0-rc.2` |
| KB Lifecycle | `0.2.3` |
| Container do plugin vNext | `0.1.9` |
| Engine `kb_next.py` incluído | `0.1.7` |
| Session Gate | `0.2.7` |
| Marketplace | `0.3.8` |

O engine incluído faz bootstrap de uma cópia estável em
`.kb-next/runtime/kb_next.py`. Sessões normais usam essa cópia. Upgrade e
rollback resolvem primeiro o artefato novo ou restaurado e fazem bootstrap a
partir dele. O bootstrap substitui drift de bytes com a mesma versão, reporta
SHA-256 de origem e instalado e rejeita alvos ligados ou fora do project root.
Usar o runtime atual do workspace como sua própria origem retorna
`action: self` e não prova transição de versão.

Escritas operacionais em `.kb-next/` não são escritas canônicas.
`session-start` e `lookup` anexam evidência operacional; comandos semânticos e
de wiki podem escrever manifests, propostas, drafts ou materializações. Apenas
`proposal-apply` aprovado pode cruzar para `.kb/` canônica, sempre por
`.kb/kb.py`.

## Verification / Verificação

Use `python tools\validate_vnext_product.py` para validar docs, manifesto,
inclusão do runtime nos plugins, links relativos e, opcionalmente, o ZIP. Use
`python tools\sync_vnext_runtime.py --check` para conferir a paridade do runtime.

## Troubleshooting / Solução De Problemas

Se uma plataforma se comportar diferente, confira o tipo de artefato antes de mudar runtime. Não prometa startup automático no Cowork; documente startup manual.

## Related / Relacionados

- [Instalação para admins](admin-installation.md)
- [Referência de comandos](command-reference.md)
- [Release para maintainers](maintainer-release.md)
- [Troubleshooting](troubleshooting.md)
