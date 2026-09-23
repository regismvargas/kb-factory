# Upgrade E Rollback KB/Wiki vNext

## Purpose / Propósito

Atualizar KB/Wiki vNext com segurança, preservando a memória canônica `.kb/` e mantendo rollback possível.

## Audience / Público

Admins, maintainers e donos de projeto que recebem um novo bundle controlado.

## Prerequisites / Pré-requisitos

- Estado atual do workspace commitado ou salvo em backup.
- Versão atual do pacote registrada.
- Nenhuma operação `proposal-apply` pendente e sem revisão.

## Passos

Registre o pacote atual, a versão do runtime do workspace e o namespace de
comandos:

```powershell
python .\.kb-next\runtime\kb_next.py --project-root . session-start --json
```

Para instalações de plugin, confirme também que `vnext-session-start` está
disponível e que basenames genéricos `session-start` / `session-end` estão
ausentes.

Instale o novo plugin ou descompacte o novo bundle stand-alone ao lado do
anterior. Mantenha o artefato anterior disponível. Não sobrescreva `.kb/` com o
template do bundle em um workspace existente.

Resolva o runtime a partir do **novo artefato**, nesta ordem:

1. `${CLAUDE_PLUGIN_ROOT}/runtime/kb_next.py` para o plugin recém-instalado.
2. O path do novo plugin no cliente que corresponda a
   `**/kb-wiki-vnext/runtime/kb_next.py`.
3. `runtime/kb_next.py` dentro do novo bundle stand-alone.
4. `core/versions/kb-wiki-vnext/runtime/kb_next.py` apenas no monorepo de
   autoria KB Factory.

Não use o `.kb-next/runtime/kb_next.py` atual como fonte do upgrade. Se o novo
artefato não contiver o runtime, pare e reporte um artefato incompleto.

Faça o bootstrap do workspace a partir dessa nova fonte:

```powershell
python <new-source-runtime> --project-root . bootstrap --json
```

Exija a nova `runtime_version` esperada e uma `action` igual a `created`,
`updated` ou `exists`. Exija `source_sha256` igual a `installed_sha256`; bytes
diferentes são substituídos mesmo quando a versão é igual. Uma `action` igual
a `self` não prova o upgrade, pois indica que o runtime do workspace foi usado
como sua própria fonte.

Rode os checks a partir do runtime atualizado do workspace:

```powershell
python .\.kb-next\runtime\kb_next.py --project-root . compliance-preflight --work-type operational --topic "vNext upgrade check" --json
python .\.kb-next\runtime\kb_next.py --project-root . session-start --json
python .\.kb-next\runtime\kb_next.py --project-root . semantic-hygiene --scope hot-overflow --json
```

## Upgrade Para 0.1.10 (Runtime 0.1.8)

Esta versão corrige o fluxo KB + Wiki. Projetos ativados com
`--choice kb-wiki` na 0.1.9 ou anterior ficaram com o wiki clássico desligado;
este upgrade liga o wiki e o mantém atualizado. Rode os passos na raiz de cada
projeto:

1. Atualize o motor vNext a partir do plugin novo:
   `python <new-source-runtime> --project-root . bootstrap --json`
   (espere `runtime_version` `0.1.8`).
2. Atualize o motor clássico sem tocar dados nem config:
   `python .kb-next/runtime/kb_next.py upgrade-classic --json`.
3. Reaplique a decisão registrada (`sponsor_decision` em
   `.kb-next/decisions/activation-decision.json`):
   `python .kb-next/runtime/kb_next.py activation-wizard --mode short --choice kb-wiki --json` (ou `--choice kb-alone`).
   Em `kb-wiki` isso liga `wiki.enabled` e `run_wiki_sync` nos eventos
   record-filed, source-ingest, session-end e scheduled-maintenance em
   `.kb/kb.config.json`, preserva as demais chaves, roda o primeiro `wiki-sync`
   e registra `classic-config-sync` e `classic-wiki-sync` em
   `.kb-next/operations.jsonl`. Edições em `.kb-next/kb-next.config.json`
   sobrevivem ao merge.
4. Projetos só-clássicos que já usam o wiki:
   `python .kb/kb.py wiki-config --enable --json`.
5. Normalize caminhos de fonte absolutos legados:
   `python .kb/kb.py source-relink --dry-run --json` e depois sem `--dry-run`.
6. Confira `python .kb/kb.py doctor --json`, `python .kb/kb.py wiki-check --json`
   (`wiki_state` diferente de `off` em `kb-wiki`; `publication.held_back` mostra
   cada página retida e o motivo) e `session-start --json` (`wiki.status`
   igual a `aligned`).

Mudanças de comportamento esperadas:

- Comandos além de `init` param com mensagem explícita quando falta
  `.kb/kb.db`; nada cria KB vazia em silêncio.
- Em um worktree Git vinculado, o runtime clássico usa o `.kb/` do worktree
  principal quando ele tem `kb.db`, então worktrees por sessão compartilham
  uma KB. Use `storage.worktree_scope` igual a `local` para desligar.
  `doctor --json` mostra a resolução e avisa quando o `kb.db` está versionado.
- IDs novos levam o prefixo do projeto (`<SLUG>-KB-<utc>-<hex>`). Defina
  `project.id_prefix` para trocar, ou string vazia para o formato antigo.
- Comandos de leitura não gravam mais no `kb.db`; a contagem de acesso do `get`
  é opcional (`tracking.record_access`).
- `wiki.enabled: true` liga o wiki em qualquer `activation_mode`.
- `create`, `file`, `supersede`, `resolve` e `ingest` atualizam exports e o
  wiki habilitado; use `--no-auto-lifecycle` para pular.
- Comandos novos do runtime: `install-classic`, `upgrade-classic`,
  `wiki-draft-status` e `session-hint`; `lookup`, `semantic-lookup` e
  `curation-proposal` aceitam `--domain`. O plugin ganha `vnext-wiki-drafts`.

Rollback deste upgrade: restaure o plugin anterior e rode o `bootstrap` dele
como abaixo. Volte as chaves do wiki clássico aos valores anteriores só com
aprovação, usando `changes[].from` da última entrada `classic-config-sync`, e
restaure o motor clássico anterior com
`python .kb-next/runtime/kb_next.py upgrade-classic --template <previous-scaffold-dir> --json`.

Para rollback, reinstale o ZIP anterior ou restaure o bundle stand-alone
anterior. Resolva o runtime pela mesma ladder centrada no artefato e rode:

```powershell
python <restored-source-runtime> --project-root . bootstrap --json
```

Exija a `runtime_version` anterior esperada e `source_sha256` igual a
`installed_sha256`; `action: self` não prova o rollback. Deixe `.kb/` intacto,
exceto se um maintainer restaurar explicitamente um backup do workspace.

## Verification / Verificação

O upgrade é aceitável quando o bootstrap informa a versão esperada e hashes de
origem/instalado iguais, `vnext-session-start` ou o runtime `session-start`
passa e
`.kb-next/memory/NOW.md` permanece legível. Os comandos de sessão e preflight
podem anexar evidência operacional a `.kb-next/operations.jsonl`; eles não podem
alterar a `.kb/` canônica. Compare o hash de `.kb/kb.db` antes e depois dos
checks.

## Troubleshooting / Solução De Problemas

Se o runtime novo falhar, volte ao artefato anterior e preserve o bundle com
falha para revisão. Se `.kb/` mudar inesperadamente, pare e compare o backup
antes de seguir.

## Related / Relacionados

- [Arquitetura](architecture.md)
- [Referência de comandos](command-reference.md)
- [Release para maintainers](maintainer-release.md)
- [Manual do usuário](user-manual.md)
