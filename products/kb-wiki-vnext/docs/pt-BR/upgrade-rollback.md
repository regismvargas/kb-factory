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

## Upgrade Para 0.2.1 (Runtime 0.2.1)

Esta versão acrescenta a ponte de memória para subagentes, o gate de escrita e
a curadoria automática, e marca o modelo denso multilíngue como não
recomendado. Não muda dados nem schema.

- Ponte para subagentes: a skill e o `AGENTS.md` pedem ao agente principal que
  ponha records da KB nos briefs de subagentes e que registre os
  `KB candidates` que eles relatam; o plugin do Claude Code acrescenta um hook
  `SubagentStart` (runtime `subagent-hint`).
- Gate de escrita: um hook `PreToolUse` (`scripts/write_gate.py`, Bash e
  PowerShell) nega `.kb/kb.py create`, `file`, `supersede` ou `update` vindos
  de um agente num projeto vNext e indica o caminho das propostas. O dono do
  projeto pode desligá-lo com `{"write_gate": {"enabled": false}}` em
  `.kb-next/kb-next.config.json`.
- `filing-proposal` agora bloqueia a proveniência que o `proposal-apply`
  recusaria (caminho de arquivo, URL ou id desconhecido); cite um `record_id`
  existente ou o `source_id` de um arquivo registrado com
  `python .kb/kb.py ingest <caminho> --json`.
- Curadoria: o `vnext-session-end` roda a detecção de higiene somente leitura
  e grava propostas de higiene julgadas, no máximo
  `semantic_curation.weekly_hygiene_proposals` (padrão 5) abertas por projeto
  em 7 dias; o `semantic-hygiene` reporta `review_budget`, `already_open` e
  `deferred`.
- `dense-index` e o lookup denso avisam enquanto `potion-multilingual-128M`
  estiver configurado; o modelo fica fixado até a 0.3.

1. Instale o ZIP do plugin 0.2.1 ou a entrada do marketplace; os hooks valem a
   partir da próxima sessão do Claude Code. O Codex pede confiança nos hooks
   alterados antes de rodá-los.
2. Onde o projeto fixa um runtime local, atualize-o:
   `python <new-source-runtime> --project-root . bootstrap --json`
   (espere `runtime_version` `0.2.1`).

Rollback: reinstale o plugin 0.2.0 e rode `bootstrap` a partir do runtime dele.
Nada a desfazer em `.kb/`; as propostas de higiene gravadas pela 0.2.1 ficam em
`.kb-next/proposals/hygiene` como evidência de revisão, e os hooks não escrevem
nada.

## Upgrade Para 0.2.0 (Runtime 0.2.0)

Esta versão quebra a linha de comando do `proposal-apply`: todo apply precisa
nomear quem o aprova. Ela também troca o lookup por `LIKE` por recuperação
ranqueada, corrige a consulta do `kb.py search` clássico (KB Lifecycle 0.2.5)
e acrescenta uma lista densa opcional, que ranqueia por significado. Rode os
passos na raiz de cada projeto:

1. Atualize o motor vNext a partir do plugin novo:
   `python <new-source-runtime> --project-root . bootstrap --json`
   (espere `runtime_version` `0.2.0`).
2. Atualize o motor clássico sem tocar dados nem config:
   `python .kb-next/runtime/kb_next.py upgrade-classic --json`.
3. Acrescente `--actor <id>` e `--actor-runtime <claude-code|codex|cowork|human>`
   a todo script, alias ou prompt salvo que chame `proposal-apply`.
   `--actor` é a pessoa que aprovou a proposta; `--actor-runtime` é o runtime
   que executa o apply (`human` quando uma pessoa o roda à mão):

```powershell
$proposalId = 'replace-with-reviewed-proposal-id'
$approver = 'replace-with-approver-id'
python .\.kb-next\runtime\kb_next.py --project-root . proposal-apply --proposal $proposalId --approve --approval-note "Approved after review" --actor $approver --actor-runtime human --json
```

   Um projeto com um aprovador habitual pode, em vez disso, nomear essa pessoa
   uma vez, para que o agente não pergunte a cada aprovação. Mescle esta chave
   em `.kb-next/kb-next.config.json`; o `--actor` passa a ter esse valor como
   padrão, e o `--actor-runtime` segue obrigatório:

```json
{"proposal_apply": {"default_actor": "replace-with-approver-id"}}
```

4. Opcional, para projetos que querem a lista densa: instale o extra no Python
   que roda o runtime, escolha o modelo e construa o índice.

```powershell
python -m pip install model2vec==0.10.0
python .\.kb-next\runtime\kb_next.py --project-root . dense-index --fetch-model --json
python .\.kb-next\runtime\kb_next.py --project-root . lookup --facet status --query "release" --limit 5 --lists words,dense --json
```

   Antes do `dense-index`, ponha `retrieval.dense.enabled` em `true` em
   `.kb-next/kb-next.config.json` e mantenha `retrieval.dense.model` em
   `potion-base-32M` (o padrão), para que o índice seja construído com esse
   modelo. `potion-multilingual-128M` não é recomendado: um lookup a frio na
   linha de comando custa cerca de 11,7 s com ele, contra 0,5 s só com
   palavras, e a expansão de consulta pelo agente alcança os mesmos sinônimos
   em português sem custo. Ele fica fixado até a 0.3 para que índices
   existentes continuem carregando, e `dense-index` e `lookup` imprimem um
   aviso enquanto ele estiver configurado. O modelo é baixado uma vez para `~/.cache/kb-factory/models` (ou
   `KBF_MODEL_CACHE`), fora do projeto, e `.kb-next/index/` se ignora no Git.
   A verificação com `lookup` precisa listar `dense` em `retrieval.lists`, sem
   aviso. Rode `python .kb-next/runtime/kb_next.py dense-index --json` de novo
   depois de registrar records; até lá o lookup avisa quantos records a lista
   densa não vê. O comando de plugin `vnext-session-end` faz essa atualização
   quando a lista densa está ligada e a sessão mudou records.

Mudanças de comportamento esperadas:

- `proposal-apply` sem `--actor` (e sem `proposal_apply.default_actor` na
  config) ou sem `--actor-runtime` sai com código 2 antes de ler a proposta e
  não grava nada; o stderr nomeia as flags que faltam. Um `--actor` em branco
  ou um runtime fora dos quatro valores falha do mesmo jeito; um
  `default_actor` em branco ou que não seja texto falha com código 1, também
  antes de qualquer escrita.
- Cada manifest de apply em `.kb-next/manifests/proposal-apply`, cada entrada
  `proposal-apply` em `.kb-next/operations.jsonl` e o resultado JSON trazem
  `actor: {id, runtime}` e `actor_source` (`flag` ou `config`), inclusive
  tentativas bloqueadas. A identidade é registrada, não autenticada. Nenhum
  comando do runtime grava `proposal_apply.default_actor`; a ativação o
  preserva.
- Os manifests de LLM deixam de trazer o ator fixo de placeholder.
  `semantic-lookup`, `curation-proposal`, `semantic-hygiene`, `filing-proposal`
  e `wiki-synthesis-plan` aceitam o mesmo par como opção e registram quem gerou
  a proposta, ou `actor: null` sem ele; uma flag sozinha falha. O padrão da
  config vale só para o `proposal-apply`.
- Manifests e entradas do oplog gravados antes da 0.2.0 mantêm o formato
  antigo. Quem lê `actor` precisa aceitar a string legada, `null` e o objeto
  `{id, runtime}`.
- `lookup` e os comandos de proposta ranqueiam por uma lista FTS5 de palavras
  com BM25, por Reciprocal Rank Fusion; a ordem dos resultados muda, os termos
  são unidos por OR e a saída traz um bloco `retrieval`. A lista trigram de
  substrings é opcional (`--lists words,trigram`) e não entra na fusão padrão.
- Com `retrieval.dense.enabled`, o lookup também funde a lista densa. Um lookup
  a frio pela linha de comando leva cerca de 3 s a mais com `potion-base-32M` e
  cerca de 11 s a mais com `potion-multilingual-128M`, quase todo para carregar
  e conferir o modelo (medido numa KB de 446 records). Sem o extra, o modelo ou um índice atual, o lookup
  ranqueia por palavras e diz por quê em `retrieval.warnings`. A instalação
  padrão nunca importa o extra.
- O `kb.py search` clássico compila a consulta como a lista de palavras do
  vNext: um `?` no fim ou um `-` não derrubam mais a busca para um `LIKE` da
  frase inteira, e os resultados FTS5 saem ordenados por BM25. A saída JSON
  do `kb.py` agora escapa caracteres fora do ASCII (`\uXXXX`): um parser
  JSON lê os mesmos valores, e um console Windows com saída redirecionada não
  falha mais neles.

Rollback deste upgrade: restaure o plugin 0.1.10 e rode o `bootstrap` dele
como abaixo; depois remova `--actor` e `--actor-runtime` dos seus scripts,
porque o runtime 0.1.8 os rejeita como argumentos não reconhecidos. O runtime
0.1.8 ignora as chaves `retrieval.dense` e `proposal_apply`, e
`.kb-next/index/` pode ser apagado. O motor clássico não muda de schema: mantenha
o 0.2.5 ou volte ao 0.2.4 com o `upgrade-classic` do plugin antigo.

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
   Um `.kb-next/memory/NOW.md` curado é preservado (só o template gerado é
   regenerado) e reaplicar o mesmo modo mantém `decided_at` e `rationale`
   registrados, acrescentando `reconfirmed_at`; o JSON informa `now.action` e
   `decision`.
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
