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

## Upgrade Para 0.2.4 (Runtime 0.2.4)

Esta versão encurta o início e o fim de toda sessão e preserva os bytes das
fontes sob qualquer configuração de fim de linha. Sai com KB Lifecycle 0.2.8
e Session Gate 0.2.10. Não muda dados nem schema. A recusa de escrita no
motor clássico (E3.4) não está nesta versão.

Início e fim de sessão enxutos:

- Com o hook SessionStart, o `session-hint` é o início da sessão: traz o modo
  de ativação, a raiz da KB clássica, o cabeçalho do NOW clássico com o
  horário `Generated`, o estado da wiki, as leituras sob demanda e a folha de
  comandos. O agente lê `.kb-next/memory/NOW.md` só quando o hint diz que a
  equipe o escreveu. Clientes sem o hook (Codex antes da confiança no hook,
  Cowork) seguem com `vnext-session-start` ou `gate-session-start`.
- `vnext-session-end` e `gate-session-end` registram o que o usuário aprovou,
  rodam `python .kb/kb.py lifecycle session-end --json` uma vez e depois
  `wiki-draft-status` quando KB + Wiki está ativa e não dormente: uma chamada
  só com KB, duas com wiki ativa. A curadoria roda na manutenção semanal; uma
  manutenção completa pedida pelo usuário no fechamento continua gravando só
  propostas.
- O `session-hint` acrescenta uma linha `Curation overdue` quando a checagem
  somente leitura mais recente do `semantic-hygiene` tem mais de 7 dias. Um
  runtime anterior ao 0.2.4 não registra a checagem, então a linha aparece até
  o `bootstrap` do runtime do projeto e a próxima rodada semanal.

Fontes preservam os bytes:

- O `.kb/.gitattributes` do template traz `sources/** -text`, então o Git não
  converte mais o fim de linha das fontes, qualquer que seja o `text=auto`,
  o `eol=lf` ou o `core.autocrlf` do repositório. O SHA-256 que a KB guarda de
  cada fonte continua valendo em qualquer clone.

1. Instale o plugin vNext 0.2.4, o KB Lifecycle 0.2.8 e o Session Gate 0.2.10
   (ZIPs ou entradas do marketplace) e reinicie o cliente.
2. Onde o projeto fixa um runtime local, atualize-o:
   `python <runtime-novo> --project-root . bootstrap --json`
   (espere `runtime_version` `0.2.4`).
3. Acrescente a regra das fontes: `python .kb-next/runtime/kb_next.py upgrade-classic --json`
   (espere `gitattributes_updated` `true` uma vez). Os arquivos do motor
   clássico não mudam nesta versão.
4. Guarde os bytes das fontes que a KB hasheou. Primeiro confira que
   `git status -- .kb/sources` está vazio: faça commit ou separe qualquer
   mudança que você mesmo fez ali, para que o passo seguinte só prepare fins de
   linha. O cache de stat do Git esconde a mudança que a regra provoca, então
   rode `git add --renormalize -- .kb/sources`. Antes do commit, confira que
   `git diff --cached --ignore-cr-at-eol -- .kb/sources` não mostra nada: as
   fontes preparadas só diferem da cópia do Git no fim de linha. Se mostrar
   algo, pare, rode `git restore --staged -- .kb/sources` e revise esses
   arquivos. Do contrário, faça commit do `.kb/.gitattributes` com as fontes
   preparadas e com os arquivos de runtime atualizados.
5. Confira os hashes: `python .kb/kb.py source-verify --json`. A regra evita
   conversões novas; não repara uma fonte que um checkout já converteu. Para um
   `hash_mismatch` que reste numa fonte de texto, guarde uma cópia do arquivo,
   converta-o para o outro fim de linha (CRLF para LF ou LF para CRLF) e rode o
   `source-verify` de novo. Se a divergência sumir, esses são os bytes que a KB
   registrou na ingestão: faça commit deles. Se continuar, devolva a cópia. A
   causa fica indeterminada (a fonte pode ter fins de linha mistos, ou o
   conteúdo mudou): compare com o arquivo original ou com um backup antes de
   mexer no record.
6. Rode `python .kb-next/runtime/kb_next.py session-start --json` uma vez e
   confira que o `git status` não lista mudança nova em `.kb-next/`.

Rollback: reinstale os plugins da v0.2.3 (kb-wiki-vnext 0.2.3, KB Lifecycle
0.2.7, Session Gate 0.2.9) a partir do release público v0.2.3 e rode o
`bootstrap` do runtime 0.2.3. Os comandos de sessão voltam ao início e ao fim
mais longos. O `.kb/.gitattributes` pode ficar: removê-lo deixa o Git converter
de novo o fim de linha das fontes. Nada mais a desfazer em `.kb/`.

## Upgrade Para 0.2.3 (Runtime 0.2.3)

Esta versão traz a decisão 12 de 2026-10-21 (gate de escrita e aposentadoria
governada), que ficou fora do corte da 0.2.2, e três mudanças posteriores:
menos arquivos derivados por record, com um snapshot da wiki por página por
dia (PR #41), os seeds do template em português (PR #40) e o NOW da wiki
dormente (PR #42). Sai junto com o KB Lifecycle 0.2.7 e o Session Gate
0.2.9. Não muda dados nem schema.

Gate de escrita e aposentadoria governada (decisão 12 de 2026-10-21):

- O Codex só roda o hook PreToolUse do plugin depois que o usuário confia
  nele. Uma sonda ao vivo em 2026-10-21 (codex-cli 0.156.1, Windows) viu duas
  chamadas diretas de `kb.py create` gravarem records sem confiança; com a
  confiança contornada numa execução, o hook disparou em toda chamada de
  shell e negou o create. O Codex manda `tool_name` `Bash` com o comando cru,
  então o gate não precisa de parse específico para o Codex. Isso corrige o
  known issue da v0.2.1: a forma embrulhada em PowerShell que ele cita
  aparece só no event stream do `codex exec --json`, nunca no payload do
  hook. O problema é a confiança que falta.
- O gate também nega `kb.py resolve`, `bulk-import`, `init --seed`,
  `raw-query --allow-write`, `consolidate --apply-demotions`,
  `lifecycle scheduled-maintenance` e qualquer evento de `lifecycle` com
  `--apply-demotions` ou `--apply-cold-demotions`. `ingest`, eventos de
  `lifecycle` sem essas flags, `wiki-*`, `export`, `--help` e leituras seguem
  livres. Ele lê as formas de chamada que um agente digita (`env`,
  `python -m kb`, `cmd /c`, `powershell -Command`, `bash -lc`,
  `Start-Process`, `Invoke-Expression`, continuações de linha), segue `cd`,
  `Set-Location`,
  `pushd` e `popd` literais e põe gate num worktree Git vinculado quando ele
  ou o checkout principal está ativado; a guarda de demoção do clássico usa
  a mesma regra.
- `proposal-apply --target-record-id` não move mais uma proposta aprovada
  para outro record. Para `demote_hot`, `resolve` e `retire` ele precisa
  repetir o alvo da proposta; para `supersede` só pode escolher um dos
  candidatos a duplicata que a proposta cita. Qualquer outro valor bloqueia
  com `invalid_target_override`. Runtimes anteriores, a 0.2.2 e a 0.2.1 inclusive,
  aplicavam uma proposta aprovada ao record que a flag indicasse.
- Nova ação de higiene `retire`: um record que outro record ATIVO já substitui
  vai para `supersede_or_merge_candidate` com `"action": "retire"` e
  `replacement_id`; o `proposal-apply` roda o `supersede` clássico com
  `--replacement-id` (KB Lifecycle 0.2.7), que o marca SUPERSEDIDO sem criar
  record. RESOLVIDO continua só para pendências
  (PENDENCIA).
- O KB Lifecycle 0.2.7 pula as demoções automáticas de HOT e COLD num projeto
  com `.kb-next/kb-next.config.json`, venham da config ou de flags, e reporta
  `demotions_skipped`. Projetos só clássicos mantêm as demoções.
- O Session Gate 0.2.9 deixa de rodar `scheduled-maintenance --apply-demotions`
  num workspace vNext e roda o passo de curadoria do vNext no lugar.

Arquivos derivados e correções:

- Exports e wiki só reescrevem um arquivo derivado quando o conteúdo muda
  (o carimbo `Generated` sozinho não conta mais), então um filing toca
  cerca de metade dos arquivos de antes. Uma página substituída fica em
  `wiki/snapshots` uma vez por página por dia UTC, e não a cada
  renderização; o histórico completo segue nos records, no `audit_log`, no
  oplog e no Git.
- O `session-hint` termina com uma folha de cinco comandos do projeto, e o
  `--help` lista os comandos do dia a dia; o `--help-all` mostra tudo.
- Os cinco seeds do template em português achados no portfólio saem de
  NOW, HOT e INDEX, como os em inglês, no próximo export.
- O NOW de uma wiki dormente diz quando a wiki começa e aponta o
  `session-start` para o estado atual.

1. Instale o plugin vNext 0.2.3, o KB Lifecycle 0.2.7 e o Session Gate 0.2.9
   (ZIPs ou entradas do marketplace).
2. Onde o projeto fixa um runtime local, atualize-o:
   `python <new-source-runtime> --project-root . bootstrap --json`
   (espere `runtime_version` `0.2.3`).
3. Atualize o motor clássico, de que o `retire` e a guarda de demoção
   precisam:
   `python .kb-next/runtime/kb_next.py upgrade-classic --json`
   (depois disso `supersede --help` lista `--replacement-id`). Com um motor
   anterior, o `proposal-apply` bloqueia o `retire` com um aviso que cita
   `upgrade-classic`.
4. Onde o projeto versiona `.kb-next/runtime/kb_next.py` ou `.kb/runtime/`,
   faça commit dos arquivos atualizados. Até esse commit entrar, todo outro
   clone ou worktree do projeto roda o runtime e o motor 0.2.2 versionados.
   Depois rode `python .kb-next/runtime/kb_next.py session-start --json` uma
   vez e confira que o `git status` não lista mudança nova sob `.kb-next/`.
5. Só no Codex: confie nos hooks do plugin na revisão de hooks do Codex. O
   Codex 0.156.1 só roda um hook de plugin depois dessa confiança, e um hook
   sem confiança não deixa rastro no `codex exec --json`. Confira que a
   confiança do PreToolUse ficou registrada:
   `Select-String -Path "$HOME\.codex\config.toml" -Pattern 'kb-wiki-vnext@.*pre_tool_use'`
   Esta versão não muda os comandos de hook em `hooks/hooks.json`. Se uma
   mudança futura neles faz o Codex pedir confiança de novo é hipótese da
   sonda de 2026-10-21, não verificada. A confiança persistida ainda não foi
   testada; até o aceite abaixo passar, trate o gate no Codex como não
   verificado.
   Aceite, num sandbox descartável e nunca num projeto do portfólio
   (`$runtime` é o runtime do plugin instalado; a contagem de records não
   pode mudar e o event stream precisa mostrar o bloqueio):

   ```powershell
   $runtime = "$HOME\.codex\plugins\cache\kb-factory-tools\kb-wiki-vnext\0.2.3\runtime\kb_next.py"
   New-Item -ItemType Directory trust-check | Set-Location
   git init
   python $runtime --project-root . install-classic --slug trustcheck --domains general --json
   python $runtime --project-root . bootstrap --json
   python $runtime --project-root . activation-wizard --mode short --choice kb-alone --json
   Set-Content prompt.txt 'Run exactly one shell command and nothing else: python .kb/kb.py create --category FATO --domain general --title "Gate check" --content "Codex trust check" --source check --json'
   Get-Content prompt.txt | codex exec -C . --ephemeral --json - | Select-String 'Command blocked by PreToolUse hook'
   python -c "import sqlite3; print(sqlite3.connect('.kb/kb.db').execute('SELECT COUNT(*) FROM records').fetchone()[0])"
   ```

   Um record a mais do que depois do `install-classic` significa que a
   confiança não pegou.

Rollback: reinstale os plugins da v0.2.2 (kb-wiki-vnext 0.2.2, KB Lifecycle
0.2.6, Session Gate 0.2.8) a partir da release pública v0.2.2 e rode
`bootstrap` com o runtime 0.2.2. Depois rode o `upgrade-classic` dele com
`--template` apontando para a pasta do scaffold do KB Lifecycle 0.2.6 dessa
release: sem isso, um cache de plugin que ainda tem a 0.2.7 é escolhido como
o scaffold mais novo e o motor 0.2.7 volta. Confira que `python .kb/kb.py
supersede --help` não lista mais `--replacement-id`. Nada a desfazer em
`.kb/`. Records aposentados pela 0.2.3 continuam
SUPERSEDIDO, que um motor clássico anterior lê como qualquer record
substituído; com o motor 0.2.6, as demoções automáticas voltam a rodar em
projetos vNext.

## Upgrade Para 0.2.2 (Runtime 0.2.2)

Esta versão tira a telemetria de leitura da trilha de governança versionada e
corrige o comando `session-start` que o `session-hint` imprime. Não muda dados
nem schema.

- `session-start`, `lookup`, `semantic-lookup` e `dense-index` anexam seus
  eventos em `.kb-next/telemetry/events.jsonl` em vez de
  `.kb-next/operations.jsonl`, então uma sessão deixa de alterar arquivo
  versionado. O diretório de telemetria se ignora pelo próprio `.gitignore`,
  gravado uma única vez pelo `activation-wizard` ou pelo primeiro append de
  telemetria; o `.gitignore` do projeto não é editado. O arquivo gira para
  `events.1.jsonl` ao atingir 1 MiB.
- Os dois arquivos são gravados com fim de linha LF também no Windows. As
  linhas existentes em `.kb-next/operations.jsonl` não são reescritas: eventos
  de leitura e linhas CRLF de runtimes anteriores ficam como histórico.
- O `session-hint` indica um runtime que existe quando `.kb-next/runtime/` está
  ausente e acrescenta uma linha `Runtime skew` quando a versão do runtime
  local difere da do plugin.

Onboarding enxuto (PR #37), nesta versão:

- Seeds do template. O scaffold clássico do KB Lifecycle 0.2.6 não semeia
  nenhum record. Uma KB criada antes mantém seus cinco seeds do template no
  `kb.db` e na busca; NOW, HOT, INDEX, topics, packs, candidatos e sinais da
  wiki e os tópicos de wiki do vNext os deixam de fora a partir da próxima
  atualização dessas superfícies, que `python .kb/kb.py export` (ou qualquer
  `lifecycle session-end`) roda.
- Escopo. `activation-wizard --scope "<escopo nas palavras do usuário>"`
  registra o escopo uma vez como `DECISAO` HOT com a tag `project-scope`, sem
  `valid_until`. Sem `--scope`, nenhum record é criado.
- Wiki dormente. Uma ativação `kb-wiki` com menos de
  `--wiki-min-sourced-records` (padrão 10) records ativos que citam uma fonte
  registrada deixa a wiki clássica dormente (modo `signal`): sem páginas, sem
  a linha de drafts no hook, `wiki.status` `dormant`. O record que cruza o
  limiar publica as primeiras páginas. Uma wiki clássica já ligada continua
  ligada; para publicar na hora numa ativação nova, passe
  `--wiki-min-sourced-records 0`.
- Uma chamada para um record aprovado no chat. O `approved-filing` o registra
  com as regras do `proposal-apply` (proveniência, piso de confiança, alvo de
  supersede ativo) mais uma checagem de título repetido, um manifest em
  `.kb-next/manifests/approved-filing/` e uma linha no oplog; uma chamada
  bloqueada não grava nada e sai com 1. Um supersede pode mudar a categoria e
  limpar `valid_until` (`--valid-until none`); mudar a categoria exige o
  clássico 0.2.6 (`supersede --category`); na 0.2.2 só o `approved-filing` a
  repassa (o `proposal-apply` repassa a partir da 0.2.3).
- Confiança da wiki por record. Um record abaixo de
  `min_confidence_autopublish` sai da página em vez de reter a página
  inteira; a página só fica retida quando não sobra nenhum record, e
  `wiki-sync` e `wiki-check` listam os records deixados de fora em
  `records_held_back`. Depois do `upgrade-classic`, o próximo `wiki-sync`
  pode publicar páginas que a 0.2.1 retinha.

1. Instale o ZIP do plugin 0.2.2 ou a entrada do marketplace.
2. Onde o projeto fixa um runtime local, atualize-o:
   `python <new-source-runtime> --project-root . bootstrap --json`
   (espere `runtime_version` `0.2.2`).
3. Onde o projeto versiona `.kb-next/runtime/kb_next.py`, faça commit do
   runtime atualizado junto com as linhas do oplog que sessões da 0.2.1
   deixaram sem commit. Depois rode
   `python .kb-next/runtime/kb_next.py session-start --json` uma vez e confira
   que o `git status` não lista mudança nova em `.kb-next/`.

Rollback: reinstale o plugin 0.2.1 da release pública v0.2.1 e rode `bootstrap`
a partir do runtime dele. Nada a desfazer em `.kb/`; os eventos de leitura voltam para
`.kb-next/operations.jsonl`, e `.kb-next/telemetry/` pode ser apagado.

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
`.kb-next/memory/NOW.md` permanece legível. Os comandos de sessão anexam
telemetria de leitura ao `.kb-next/telemetry/events.jsonl`, ignorado pelo Git, e o
preflight não escreve nada; eles não podem alterar a `.kb/` canônica. Compare o hash de `.kb/kb.db` antes e depois dos
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
