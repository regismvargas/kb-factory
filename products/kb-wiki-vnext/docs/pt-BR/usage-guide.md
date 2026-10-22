# Guia De Uso KB/Wiki vNext

## Purpose / Propósito

Explicar como usar cada comando do runtime KB/Wiki vNext em projetos reais e em conversas com agentes.

## Audience / Público

Usuários, admins e maintainers que precisam ir além da instalação: quando usar cada feature, o que pedir ao agente e como evitar mudanças acidentais na memória canônica.

## Prerequisites / Pré-requisitos

- KB/Wiki vNext `0.2.0-rc.6` instalado por ZIP de plugin ou bundle stand-alone.
- Identidade de componentes registrada pelo maintainer: produto `0.2.0-rc.6`,
  KB Lifecycle `0.2.5`, container de plugin `0.2.2`, runtime incluído `0.2.2`,
  Session Gate `0.2.8` e marketplace `0.3.13`.
- Workspace com `.kb/` disponível como memória canônica.
- Python disponível como `python`.
- Acordo de que `.kb-next/` é memória operacional, evidência de proposta e materialização de drafts, não fonte canônica.

## Mental Model / Modelo Mental

`.kb/` permanece canônico. Ele guarda a memória durável do projeto e é a única camada que deve ser tratada como fonte de verdade. KB/Wiki vNext lê `.kb/` por caminhos suportados do runtime, e apenas `proposal-apply` pode levar uma proposta aprovada de volta para `.kb/` por meio de `.kb/kb.py`.

`.kb-next/` é a camada de trabalho. Ela guarda decisões de ativação, pistas de sessão, propostas semânticas, manifests de inferência, drafts de wiki, superfícies materializadas de revisão, exports de adapters e evidência operacional. Ela existe para ajudar agentes a trabalhar com contexto fino e revisável, sem carregar todo o histórico por padrão.

Comandos descritos como read-only são read-only contra o `.kb/` canônico. `.kb-next/operations.jsonl` é a trilha de governança e é versionado com o projeto: registra mutações e decisões (ativação e sincronização clássica, propostas, `proposal-apply`, revisão e materialização da wiki, exports, instalação e upgrade do clássico). Comandos de leitura (`session-start`, `lookup`, `semantic-lookup`) e o build derivado do `dense-index` anexam seus eventos em `.kb-next/telemetry/events.jsonl`; o `semantic-lookup` continua gravando seu manifest e sua proposta de resposta em `.kb-next/`. O diretório de telemetria se ignora pelo próprio `.kb-next/telemetry/.gitignore`, que o `activation-wizard` ou o primeiro append de telemetria grava uma única vez; o `.gitignore` do projeto nunca é editado. O arquivo gira para `events.1.jsonl` ao atingir 1 MiB e mantém uma geração anterior (cerca de 2 MiB em disco enquanto a rotação funciona); uma falha na rotação ou na gravação da telemetria nunca derruba o comando de leitura. A partir do runtime 0.2.2 os dois arquivos são gravados com fim de linha LF em qualquer plataforma; as linhas gravadas por runtimes anteriores, incluindo eventos de leitura e finais CRLF, ficam na trilha como histórico.

Resumo de mutações:

| Família de comandos | `.kb/` | `.kb-next/` |
|---|---|---|
| `bootstrap` | sem mudança | instala apenas `runtime/kb_next.py` |
| `install-classic`, `upgrade-classic` | `install-classic` cria a `.kb/` ausente a partir do scaffold clássico e roda o `init` clássico; `upgrade-classic` substitui apenas `kb.py` e `runtime/*.py` | append de evidência operacional |
| `compliance-preflight`, `source-linkage-audit`, `semantic-hygiene` padrão, `wiki-draft-status`, `session-hint`, `subagent-hint` | read-only | sem escrita |
| `session-start`, `lookup` | read-only | append de telemetria de leitura em `.kb-next/telemetry/events.jsonl` |
| ativação, semântica, propostas, export e wiki | read-only, exceto `activation-wizard`: `--choice kb-wiki` grava as chaves da wiki clássica em `.kb/kb.config.json` e roda o primeiro `wiki-sync` (publica `.kb/wiki/live`); `--disable-classic-wiki` desliga a wiki clássica | escreve config, manifests, propostas, drafts, exports ou evidência operacional governada |
| `proposal-apply` aprovado | muta apenas por `.kb/kb.py` | escreve evidência de apply e operações |

Use o layout do repositório ao rodar deste repo:

```powershell
python core\versions\kb-wiki-vnext\runtime\kb_next.py <command>
```

Use o layout stand-alone ao rodar do bundle descompactado:

```powershell
python runtime\kb_next.py <command>
```

Para um plugin instalado, trate `vnext-session-start` como basename lógico.
Claude Code invoca `/kb-wiki-vnext:vnext-session-start`; Codex invoca
principalmente o skill embutido `kb-wiki-vnext`; Cowork usa a ação namespaced
realmente exposta pela UI do plugin ou o skill em linguagem natural. No shell,
resolva um engine executável nesta ordem:

1. `./.kb-next/runtime/kb_next.py` em workspace já inicializado.
2. `${CLAUDE_PLUGIN_ROOT}/runtime/kb_next.py` para o plugin Claude ativo.
3. O caminho do plugin instalado no Codex, Cowork ou Claude que corresponda a
   `**/kb-wiki-vnext/runtime/kb_next.py`.
4. `core/versions/kb-wiki-vnext/runtime/kb_next.py` apenas no monorepo de
   autoria KB Factory.

Quando o primeiro caminho não existir, instale o engine resolvido no workspace:

```powershell
python <plugin-runtime-path> --project-root . bootstrap --json
python .kb-next\runtime\kb_next.py <command>
```

Em sessões normais, prefira o runtime do workspace. Em upgrade ou rollback,
faça bootstrap a partir do runtime do novo plugin instalado, nunca a partir do
próprio runtime já existente no workspace.

## Daily Conversation Workflow / Fluxo Diário De Conversa

Comece toda conversa nova de forma fina:

```powershell
python .kb-next\runtime\kb_next.py session-start --json
```

Depois leia apenas `.kb-next/memory/NOW.md` por padrão. Peça ao agente para ampliar contexto somente quando a tarefa exigir.

Bom prompt de conversa:

```text
Use a superfície KB/Wiki vNext deste cliente. No Claude Code rode `/kb-wiki-vnext:vnext-session-start`; no Codex invoque o skill `kb-wiki-vnext`. Leia apenas .kb-next/memory/NOW.md por padrão e responda via lookup antes de abrir histórico mais amplo.
```

Peça lookup determinístico quando precisar de status, decisões, definições, aprendizados ou pendências:

```text
Use vNext lookup para encontrar a decisão atual sobre ativação da wiki. Não varra o repo inteiro se o lookup for suficiente.
```

Pare e peça aprovação explícita quando a ação criar proposta, escrever draft, materializar revisão ou aplicar memória canônica.

## Project Lifecycle Workflows / Fluxos Do Ciclo De Vida Do Projeto

Projeto novo:

1. Se a pasta `.kb/` estiver ausente, crie-a com o `install-classic` do runtime (`--name`, `--slug`, `--domains`); uma `.kb/` KB Factory existente é usada como está.
2. Rode `activation-wizard`.
3. Rode `python <caminho-do-runtime> session-start --json`.
4. Use `lookup` primeiro; use comandos semânticos apenas quando houver julgamento LLM fornecido ou revisável.

Projeto existente:

1. Rode `python <caminho-do-runtime> session-start --json`.
2. Leia `.kb-next/memory/NOW.md`.
3. Use `compliance-preflight` antes de planejamento, packaging, release ou desenvolvimento.
4. Use `proposal-apply` apenas depois de aprovação humana.

Auditoria e release:

1. Rode `compliance-preflight`.
2. Rode `source-linkage-audit` quando wiki/export externo depender de vínculos de fonte canônica.
3. Rode build e validadores de produto.
4. Registre hashes e evidência no dossier da execução.

Curadoria de memória:

1. Use `lookup` ou `semantic-lookup` para recuperar evidência.
2. Use `curation-proposal`, `filing-proposal` ou `semantic-hygiene` para preparar propostas.
3. Revise a proposta e o manifest.
4. Aplique somente com `proposal-apply --approve --approval-note --actor --actor-runtime`.

Trabalho de draft de wiki:

1. Use `wiki-synthesis-plan --write-drafts`.
2. Revise drafts machine e human.
3. Use `wiki-draft-review --materialize` apenas para materialização de revisão em `.kb-next/`.
4. Não publique em `.kb/wiki/live` como parte do vNext.

Upgrade e rollback:

1. Registre pacote/runtime atual.
2. Instale o novo plugin ou descompacte o bundle stand-alone ao lado do anterior.
3. Faça bootstrap a partir do novo artefato e rode
   `python <caminho-do-runtime> session-start --json`,
   `compliance-preflight` e `semantic-hygiene` no modo report-only padrão.
4. Para rollback, reinstale o artefato anterior e faça bootstrap a partir do
   runtime dele. Não use o runtime atual do workspace como sua própria fonte de
   upgrade ou rollback.

## Command Reference / Referência De Comandos

### `bootstrap`

Propósito: instalar o runtime que executa o comando em
`.kb-next/runtime/kb_next.py` no project root selecionado.

Use quando: ativar, reparar, atualizar ou reverter um workspace consumer.

Não use quando: o runtime de origem for o mesmo runtime do workspace que você
quer substituir; `action: self` não prova upgrade ou rollback.

Exemplo com origem no plugin ou stand-alone:

```powershell
python <artifact-runtime-path> --project-root . bootstrap --json
```

Saída esperada: `runtime_version`, caminho alvo e `action` igual a `created`,
`updated` ou `exists`, além de `source_sha256` igual a `installed_sha256`.
Drift de bytes com a mesma versão é substituído. O comando escreve apenas o
arquivo de runtime do workspace; não cria config, memória, propostas ou
evidência operacional.

Riscos: bootstrap a partir de artefato antigo ou não verificado instala aquela
versão exata. Confirme identidade e hash do artefato antes.

### `install-classic`

Propósito: criar a `.kb/` clássica de um projeto novo a partir do scaffold
clássico e rodar o `init` clássico.

Use quando: um workspace novo ainda não tem `.kb/`.

Não use quando: o projeto já tem `.kb/kb.py`; o comando então informa
`action: exists` e não muda nada. Ele recusa uma `.kb/` não vazia que não tenha
`kb.py`.

Exemplo no repositório:

```powershell
python core\versions\kb-wiki-vnext\runtime\kb_next.py --project-root ..\acme install-classic --name "Acme Project" --slug acme --domains product,engineering --json
```

Exemplo stand-alone:

```powershell
python runtime\kb_next.py --project-root ..\acme install-classic --name "Acme Project" --slug acme --domains product,engineering --json
```

Saída esperada: `action: created`, o `template` usado, `files_copied` e
`seed_imported`. O scaffold vem de `--template`, do `classic-template/.kb/` do
stand-alone, do scaffold do kb-lifecycle ao lado do plugin ou no cache do
cliente, ou de `core/templates/kb/` no repo de autoria. `--no-seed` pula os
registros seed do scaffold.

Riscos: `--slug` vira o prefixo dos IDs de registro, salvo `--id-prefix`; peça
ao dono do projeto nome, slug e domínios em vez de inventá-los. Um `init`
clássico que falha remove a `.kb/` copiada.

### `upgrade-classic`

Propósito: atualizar o engine clássico (`.kb/kb.py` e `.kb/runtime/*.py`) a
partir do scaffold clássico.

Use quando: um scaffold kb-lifecycle ou bundle stand-alone mais novo traz
correções de engine para uma `.kb/` existente.

Não use quando: `.kb/` ainda não existe; use `install-classic`.

Exemplo no repositório:

```powershell
python core\versions\kb-wiki-vnext\runtime\kb_next.py --project-root ..\acme upgrade-classic --json
```

Exemplo stand-alone:

```powershell
python runtime\kb_next.py --project-root ..\acme upgrade-classic --json
```

Saída esperada: `action` igual a `updated` ou `unchanged`, o `template` usado,
`changed_files`, `gitignore_added` e `kb_py_sha256`. Dados e config (`kb.db`,
`memory/`, `sources/`, `wiki/`, `exports/`, `seed/`, `kb.config.json`) ficam
intactos; um `.kb/.gitignore` ausente é adicionado.

Riscos: o primeiro scaffold encontrado fornece o engine; passe `--template`
quando houver várias versões instaladas e você precisar de uma específica.

### `activation-wizard`

Propósito: escolher e registrar se o workspace opera como KB-only ou KB + Wiki.

Use quando: estiver configurando `.kb-next/` em um workspace ou revisitando modo de ativação com intenção do sponsor.

Não use quando: você só precisa iniciar uma conversa normal; use o comando de plugin `vnext-session-start` ou o subcomando de runtime `session-start`.

Exemplo no repositório:

```powershell
python core\versions\kb-wiki-vnext\runtime\kb_next.py activation-wizard --mode short --choice kb_alone --json
```

Exemplo stand-alone:

```powershell
python runtime\kb_next.py activation-wizard --mode short --choice kb_alone --json
```

Prompt conversacional:

```text
Rode activation-wizard em modo short com kb_alone, exceto se o sponsor aprovou explicitamente KB + Wiki.
```

Saída esperada: JSON de decisão de ativação e superfícies bootstrap em `.kb-next/`.
Com `kb-wiki`, o JSON também informa `classic_config_sync` (chaves da wiki
clássica gravadas em `.kb/kb.config.json`) e `classic_wiki_sync` (resultado do
primeiro `wiki-sync`, `skipped` com `--no-wiki-sync`), registrados em
`.kb-next/operations.jsonl` como `classic-config-sync` e `classic-wiki-sync`.

Desde o runtime 0.2.2, uma ativação `kb-wiki` cuja KB tem menos de 10
registros ativos citando uma fonte registrada deixa a wiki clássica dormente
(`activation_mode: signal` com `eligibility.min_sourced_records`):
`wiki_dormant` informa o limiar e a contagem, `classic_wiki_sync` sai como
`skipped` com `wiki_dormant`, e o registro que cruza o limiar publica as
primeiras páginas. `--wiki-min-sourced-records <n>` define o limiar; `0` liga
a wiki na hora. Uma wiki clássica ligada nunca volta a dormir.
`--scope "<escopo nas palavras do usuário>"` registra o escopo uma vez como
`DECISAO` HOT com a tag `project-scope`; uma execução posterior informa o
registro existente.

Riscos: escolher KB + Wiki sem aprovação pode implicar um fluxo de wiki mais amplo do que o projeto autorizou.

### `session-start`

Propósito: emitir o contrato fino de startup para a conversa atual.

Basename lógico distribuído: `vnext-session-start`. Invocação no Claude Code:
`/kb-wiki-vnext:vnext-session-start`. Superfície no Codex: skill embutido.
Subcomando do runtime: `session-start`.

Use quando: iniciar toda sessão com agente.

Não use quando: você está tentando aplicar mudanças na memória canônica. Ele não escreve em `.kb/`; faz append de uma linha de telemetria de leitura em `.kb-next/telemetry/events.jsonl`, ignorado pelo Git.

Exemplo no repositório:

```powershell
python core\versions\kb-wiki-vnext\runtime\kb_next.py session-start --json
```

Exemplo stand-alone:

```powershell
python runtime\kb_next.py session-start --json
```

Prompt conversacional:

```text
Comece com a superfície vNext específica do cliente ou com o runtime `session-start` e leia apenas NOW.md antes de decidir se mais contexto é necessário.
```

Saída esperada: leituras padrão, caminho obrigatório de `NOW.md` e superfícies sob demanda.

Riscos: pular este comando costuma levar a carregamento histórico amplo e ruidoso.

### `session-hint`

Propósito: imprimir o texto do hook SessionStart para um workspace vNext.

Use quando: configurar ou conferir um hook SessionStart do cliente; o hook
SessionStart do plugin chama este subcomando onde hooks são suportados.

Não use quando: você precisa do contrato de startup em si; use o runtime `session-start`.

Exemplo no repositório:

```powershell
python core\versions\kb-wiki-vnext\runtime\kb_next.py session-hint
```

Exemplo stand-alone:

```powershell
python runtime\kb_next.py session-hint
```

Saída esperada: texto simples. Em workspace vNext ele aponta o agente para o
startup vNext e apenas para `.kb-next/memory/NOW.md`; com KB + Wiki acrescenta
o lembrete de `wiki-draft-status` para o fim da sessão. Fora de workspace vNext
não imprime nada, e o hook clássico do kb-lifecycle governa. O comando
`session-start` impresso usa `.kb-next/runtime/kb_next.py` quando o arquivo
existe e, se não existe, o runtime que imprimiu o hint, com `--project-root`.
Quando o `RUNTIME_VERSION` do runtime local difere do runtime do hint, uma
linha `Runtime skew` nomeia as duas versões: runtime local mais antigo (comum
em worktree cortado antes de um commit de upgrade) aponta para o main atual ou
`existing-project-upgrade-vnext`; runtime local mais novo aponta para atualizar
o plugin, porque `bootstrap` instalaria o runtime mais antigo por cima.

Riscos: não escreve nada. O suporte a hooks depende do cliente; onde hooks
estiverem desativados, inicie a sessão manualmente.

### `subagent-hint`

Propósito: imprimir o JSON do hook SubagentStart para um workspace vNext.

Use quando: configurar ou conferir um hook SubagentStart do cliente; o hook do
plugin do Claude Code chama este subcomando para cada subagente.

Não use quando: você quer records da KB para um brief; rode `lookup` e cole os
records sob `KB records`.

Exemplo no repositório:

```powershell
python core\versions\kb-wiki-vnext\runtime\kb_next.py subagent-hint
```

Exemplo stand-alone:

```powershell
python runtime\kb_next.py subagent-hint
```

Saída esperada: um objeto JSON com `hookSpecificOutput.additionalContext`. O
texto diz ao subagente que a sessão principal é a única que escreve na KB, que
ele não roda comandos que escrevem na KB e que o relatório termina com uma
seção `KB candidates` (cada fato, decisão ou aprendizado com a fonte, ou
`none`), salvo quando o brief fixa o formato de saída. Quando `.kb/kb.db`
existe, acrescenta um comando `lookup --facet status` completo: o
`.kb-next/runtime/kb_next.py` instalado, se houver, ou este runtime com
`--project-root`. Fora de workspace vNext, ou em qualquer erro, não imprime nada.

Riscos: não escreve nada. O hook não lê o brief, então não acrescenta records;
records escolhidos pelas palavras da descrição da tarefa saíram quase todos sem
relação numa checagem com lançamentos reais, e alguns briefs isolam o subagente
de propósito.

### `compliance-preflight`

Propósito: checar gates exigidos para um tipo de trabalho antes de planejamento ou implementação.

Use quando: fizer planning, implementation, packaging, release, Track B, checks operacionais ou trabalho desconhecido.

Não use quando: a tarefa é um lookup simples sem intenção de mudança.

Exemplo no repositório:

```powershell
python core\versions\kb-wiki-vnext\runtime\kb_next.py compliance-preflight --work-type packaging --topic "vNext package update" --json
```

Exemplo stand-alone:

```powershell
python runtime\kb_next.py compliance-preflight --work-type release --topic "vNext release validation" --json
```

Prompt conversacional:

```text
Antes de implementar, rode compliance-preflight para work-type implementation e me diga se há blockers.
```

Saída esperada: status pass/block, testes exigidos, evidência e próxima ação permitida.

Riscos: tratar preflight bloqueado como sugestão pode burlar requisitos de release ou governança.

### `source-linkage-audit`

Propósito: verificar vínculos de fonte para registros sensíveis a Track B/export.

Use quando: preparar wiki/export externo que depende de proveniência de fonte canônica.

Não use quando: você só está perguntando status do projeto.

Exemplo no repositório:

```powershell
python core\versions\kb-wiki-vnext\runtime\kb_next.py source-linkage-audit --scope track-b --json
```

Exemplo stand-alone:

```powershell
python runtime\kb_next.py source-linkage-audit --scope track-b --json
```

Prompt conversacional:

```text
Rode source-linkage-audit para Track B e resuma apenas blockers que afetam prontidão de export.
```

Saída esperada: status read-only de auditoria e blockers de source linkage.

Riscos: exportar externamente antes de resolver source linkage pode gerar proveniência fraca ou não verificável.

### `track-b-export`

Propósito: gerar export derivado de Track B para um adapter suportado.

Use quando: produzir superfícies markdown externas e revisáveis, como o piloto Obsidian static markdown.

Não use quando: você espera atualizar memória canônica ou publicar páginas de wiki live.

Exemplo no repositório:

```powershell
python core\versions\kb-wiki-vnext\runtime\kb_next.py track-b-export --adapter obsidian_static_markdown --json
```

Exemplo stand-alone:

```powershell
python runtime\kb_next.py track-b-export --adapter obsidian_static_markdown --json
```

Prompt conversacional:

```text
Exporte Track B para o adapter Obsidian static markdown como artefato derivado apenas. Não publique como canônico.
```

Saída esperada: manifest de export e caminhos derivados do adapter em `.kb-next/`.

Riscos: confundir export derivado com publicação canônica de wiki.

### `lookup`

Propósito: recuperação determinística e read-only da memória clássica.

Use quando: precisar de decisões, aprendizados, definições, pendências ou status sem varrer histórico amplo.

Não use quando: você precisa de julgamento semântico entre registros ambíguos; use `semantic-lookup`.

Exemplo no repositório:

```powershell
python core\versions\kb-wiki-vnext\runtime\kb_next.py lookup --facet decisions --query "wiki activation" --limit 5 --json
```

Exemplo stand-alone:

```powershell
python runtime\kb_next.py lookup --facet status --query "release" --limit 5 --json
```

Prompt conversacional:

```text
Use lookup para open-items sobre packaging vNext e resuma apenas registros ativos.
```

Saída esperada: registros ordenados por relevância, com `classic_kb_mode` read-only e um bloco `retrieval` que informa o método, as listas ranqueadas e os avisos. Os registros são ordenados por BM25 sobre um índice FTS5 de palavras, com acentos dobrados, via Reciprocal Rank Fusion, para que outras listas ranqueadas possam entrar depois. Os termos da consulta são literais, então identificadores como `MC-G1` ou `v0.3.1` dispensam escape; um `*` no fim pede prefixo, e singular e plural se encontram. Sem `--query`, o facet é listado por tier e recência.

Riscos: a lista de palavras não resolve sinônimos. Os termos são unidos por OR e os registros que casam mais termos sobem, então acrescente termos equivalentes na mesma consulta antes de escanear arquivos, ou ligue a lista densa opcional (veja `dense-index`). Num SQLite sem FTS5, `retrieval.method` vale `like_fallback` e os resultados são casamentos por substring, sem ordenação por relevância.

`--lists` escolhe as listas ranqueadas de uma chamada (`words`, `trigram`, `dense`, separadas por vírgula); sem ele, o lookup funde a lista de palavras e, quando `retrieval.dense.enabled` vale `true` em `.kb-next/kb-next.config.json`, a lista densa. Uma lista que não pode rodar fica de fora, com aviso em `retrieval.warnings`.

```powershell
python runtime\kb_next.py lookup --facet status --query "gasto mensal com nuvem" --limit 5 --lists words,dense --json
```

### `dense-index`

Propósito: montar ou atualizar o índice denso opcional, com o qual o lookup ordena por significado além de por palavra (E4.6).

Use quando: a lista de palavras perde paráfrases e sinônimos e a máquina pode instalar o extra: `pip install model2vec==0.10.0` (traz numpy, tokenizers, safetensors, huggingface-hub, jinja2, joblib e tqdm; sem torch). A instalação padrão continua só com a biblioteca padrão e nunca importa o extra.

Não use quando: o projeto precisa ficar offline e o modelo fixado ainda não está no cache de modelos.

Exemplo stand-alone, primeira execução (baixa o modelo fixado uma vez para `~/.cache/kb-factory/models`, ou `KBF_MODEL_CACHE`, nunca dentro do projeto):

```powershell
python runtime\kb_next.py dense-index --fetch-model --json
```

Atualizar depois de registrar records, ou recomeçar do zero:

```powershell
python runtime\kb_next.py dense-index --json
```

```powershell
python runtime\kb_next.py dense-index --rebuild --json
```

Depois, ponha `retrieval.dense.enabled` em `true` em `.kb-next/kb-next.config.json`. `retrieval.dense.model` vale `potion-base-32M` (inglês, o modelo que atingiu a meta do LongMemEval) ou `potion-multilingual-128M` (inclui português; não recomendado: cerca de 11,7 s por lookup a frio, contra 0,5 s só com palavras, e a expansão de consulta pelo agente alcança os mesmos sinônimos em português sem custo; fica fixado até a 0.3, e `dense-index` e `lookup` avisam enquanto ele estiver configurado); `chunk_words` e `chunk_stride` definem a janela dos trechos (32 e 32).

Saída esperada: contagens de records, trechos, embutidos, reaproveitados e removidos, a identidade do modelo e as versões das bibliotecas. O índice fica em `.kb-next/index/dense/` (`manifest.json` e `vectors.sqlite3`), é derivado e pode ser apagado a qualquer momento; o `.kb/kb.db` só é lido.

Riscos: records registrados ou editados depois da última montagem ficam fora da lista densa, e o lookup diz quantos em `retrieval.warnings`; atualize depois de registrar. Com a lista densa ligada, o lookup preenche o limite pedido mesmo quando nenhum record é próximo em significado; leia os resultados, não a contagem. Um índice montado com outro modelo ou outra janela é ignorado, com aviso, até ser remontado.

### `semantic-lookup`

Propósito: combinar candidatos determinísticos com julgamento LLM externo.

Use quando: o vocabulário muda, sinônimos importam ou a pergunta exige interpretação semântica.

Não use quando: você não pode fornecer ou revisar o julgamento; comece com `lookup`.

Exemplo no repositório:

```powershell
python core\versions\kb-wiki-vnext\runtime\kb_next.py semantic-lookup --query "thin startup memory" --facet decisions --limit 5 --json
```

Exemplo stand-alone:

```powershell
python runtime\kb_next.py semantic-lookup --query "how do we avoid reading too much history" --facet learnings --limit 5 --json
```

Essas são primeiras passagens executáveis. Elas retornam IDs de candidatos
determinísticos e `needs_llm_judgment`. Somente uma segunda passagem deve
adicionar `--judgment @<caminho>` ou `--judgment-json <json>`, usando payload
revisado por operador e construído com esses IDs reais.

Prompt conversacional:

```text
Use semantic-lookup apenas depois de mostrar os candidatos determinísticos e a rationale do julgamento.
```

Saída esperada: candidatos, status do julgamento, registros selecionados, confiança e conflitos.

Riscos: julgamento sem suporte ou com baixa confiança não deve virar verdade canônica.

### `curation-proposal`

Propósito: preparar proposta governada de curadoria de memória a partir de evidência de lookup e julgamento semântico.

Use quando: um registro parecer desatualizado, duplicado, enganoso ou precisar ser superseded.

Não use quando: você só precisa responder uma pergunta.

Exemplo no repositório:

```powershell
python core\versions\kb-wiki-vnext\runtime\kb_next.py curation-proposal --query "obsolete startup instructions" --facet decisions --limit 10 --json
```

Exemplo stand-alone:

```powershell
python runtime\kb_next.py curation-proposal --query "duplicate release notes" --facet learnings --limit 10 --json
```

Ambos os comandos criam evidência de revisão em `.kb-next/` e podem retornar
`needs_llm_judgment`; eles não fazem curadoria em `.kb/`. Uma segunda passagem
revisada pode usar `--judgment @<caminho>` com IDs da primeira passagem.

Prompt conversacional:

```text
Prepare uma proposta de curadoria para instruções vNext stale, mas não aplique.
```

Saída esperada: draft de proposta e manifest de inferência em `.kb-next/`.

Riscos: propostas não são canônicas até revisão e aplicação.

### `semantic-hygiene`

Propósito: inspecionar higiene semântica da memória, especialmente HOT overflow, e opcionalmente escrever propostas.

Use quando: o conjunto ativo de memória está ruidoso, duplicado, stale ou sobrecarregado.

Não use quando: você quer limpeza direta em `.kb/`; este comando prepara evidência/propostas.

Exemplo no repositório:

```powershell
python core\versions\kb-wiki-vnext\runtime\kb_next.py semantic-hygiene --scope hot-overflow --limit 50 --json
```

Exemplo stand-alone:

```powershell
python runtime\kb_next.py semantic-hygiene --scope hot-overflow --limit 50 --json
```

Essa invocação padrão é report-only. Uma segunda passagem revisada pode
adicionar `--judgment @<caminho> --write-proposals`; o julgamento deve preservar
os grupos `keep_hot`, `demote_candidate`, `supersede_or_merge_candidate`,
`resolve_candidate` e `needs_sponsor`, referenciando apenas IDs retornados na
primeira passagem.

A curadoria automática roda as duas passagens em todo `vnext-session-end` e na
manutenção semanal agendada (uma sessão de agente, porque a segunda passagem
pede julgamento), ao lado do clássico somente leitura
`python .kb/kb.py hygiene-audit --json`. A saída traz `review_budget`: as
propostas de higiene válidas dos últimos 7 dias que não foram aplicadas nem
ficaram obsoletas (`open`, `open_count`), o `weekly_limit` e o `room` que
sobra. A passagem de escrita pula um alvo que já tem proposta aberta
(`already_open`) e lista o que excede o espaço em `deferred`. O limite é
`semantic_curation.weekly_hygiene_proposals` em `.kb-next/kb-next.config.json`,
5 por projeto por padrão: os nove projetos com candidatos em 2026-10-20 chegam
então a no máximo 45 decisões por semana, o que cabe na revisão semanal de
15 minutos só se cada uma levar cerca de 20 s (premissa, não medida). Reduza o
limite quando a revisão demorar mais.

Prompt conversacional:

```text
Revise HOT overflow primeiro em modo report-only. Se houver candidatos claros, proponha mudanças, mas não aplique.
```

Saída esperada: findings report-only, `review_budget` ou IDs de proposta quando `--write-proposals` for usado.

Riscos: escrever propostas ainda não aplica nada, mas cria artefatos de revisão que precisam triagem. Uma proposta recusada não fica registrada como recusada; ela sai da fila depois de 7 dias e a detecção pode propô-la de novo.

### `filing-proposal`

Propósito: preparar proposta de novo filing canônico a partir de um objeto candidato de memória.

Use quando: uma nova decisão, aprendizado, definição, pendência ou status deve ser considerado para a KB canônica.

Não use quando: o conteúdo não tem proveniência ou deve permanecer apenas na conversa.

Exemplo no repositório:

```powershell
$candidatePath = Join-Path $env:TEMP 'kb-vnext-candidate-memory.json'
@{
  title = 'Use NOW-only startup'
  content = 'Read only .kb-next/memory/NOW.md at session start.'
  source = 'operator-reviewed usage-guide example'
} | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $candidatePath -Encoding ascii
python core\versions\kb-wiki-vnext\runtime\kb_next.py filing-proposal --input "@$candidatePath" --category DECISAO --domain architecture --json
Remove-Item -LiteralPath $candidatePath
```

Exemplo stand-alone:

```powershell
$candidatePath = Join-Path $env:TEMP 'kb-vnext-candidate-memory.json'
@{
  title = 'Use artifact-first runtime bootstrap'
  content = 'Bootstrap the workspace runtime from the installed or unpacked artifact.'
  source = 'operator-reviewed usage-guide example'
} | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $candidatePath -Encoding ascii
python runtime\kb_next.py filing-proposal --input "@$candidatePath" --category DECISAO --domain operations --json
Remove-Item -LiteralPath $candidatePath
```

Prompt conversacional:

```text
Transforme esta nova regra operacional em filing-proposal com proveniência. Não escreva em .kb/kb.db.
```

Saída esperada: proposta de filing e manifest em `.kb-next/proposals`.

A proveniência em `--judgment` segue a regra do `proposal-apply`: uma lista de
`{"record_id": "<id existente>"}` ou `{"source_id": "<id SRC>"}`. Caminho de
arquivo ou URL não é proveniência; registre o arquivo antes com
`python .kb/kb.py ingest <caminho> --json` e cite o `source_id`. Desde o
runtime 0.2.1, um julgamento cuja proveniência o `proposal-apply` recusaria
sai daqui como `blocked`, com o mesmo aviso `invalid_provenance[...]`,
`unknown_record_reference:...` ou `unknown_source_reference:...`, em vez de
`valid` e recusado no apply. Um supersede nomeia o alvo em
`record_draft.supersedes_id`.

Riscos: memória com baixa proveniência deve ser bloqueada ou ficar como evidência draft.

### `proposal-apply`

Propósito: aplicar uma proposta aprovada por meio de `.kb/kb.py`.

Use quando: uma pessoa revisou a proposta e aprovou explicitamente a mutação canônica.

Não use quando: aprovação está ausente, ambígua ou a proposta está fora de `.kb-next/proposals`.

Exemplo no repositório:

```powershell
$proposalId = 'replace-with-reviewed-proposal-id'
$approver = 'replace-with-approver-id'
python core\versions\kb-wiki-vnext\runtime\kb_next.py proposal-apply --proposal $proposalId --approve --approval-note "Approved by project owner after proposal review" --actor $approver --actor-runtime human --json
```

Exemplo stand-alone:

```powershell
$proposalPath = '.kb-next\proposals\replace-with-reviewed-proposal.json'
$approver = 'replace-with-approver-id'
python runtime\kb_next.py proposal-apply --proposal $proposalPath --approve --approval-note "Maintainer approved after review" --actor $approver --actor-runtime human --json
```

Substitua o valor da variável de exemplo pela proposta revisada retornada pelo comando
anterior. Nunca infira um ID nem reutilize uma nota de aprovação da documentação.
`--actor` nomeia quem aprova o apply e `--actor-runtime` é um de
`claude-code`, `codex`, `cowork` ou `human`. Os dois são obrigatórios desde o
runtime 0.2.0; o manifest de apply e `.kb-next/operations.jsonl` os registram.
A identidade é registrada, não autenticada.

Um projeto com um aprovador habitual pode nomear essa pessoa uma vez em
`.kb-next/kb-next.config.json`, para que o agente não pergunte a cada aprovação:

```json
{"proposal_apply": {"default_actor": "replace-with-approver-id"}}
```

Mescle essa chave à config existente. Com ela, `--actor` pode ser omitido e o
runtime registra o id configurado com `actor_source: config`; `--actor` continua
valendo quando outra pessoa aprova (`actor_source: flag`), e `--actor-runtime`
segue obrigatório. Só uma pessoa define a chave: nenhum comando do runtime a
grava, a ativação a preserva e um valor em branco faz o apply falhar.

Prompt conversacional:

```text
Aplique esta proposta apenas se ela estiver vinculada a um manifest válido e eu a tiver aprovado explicitamente nesta mensagem.
```

Saída esperada: status applied/blocked e detalhes da ponte canônica.

Riscos: este é o único comando do fluxo destinado a mutar memória canônica; use deliberadamente.

Gate de escrita: num projeto com `.kb-next/kb-next.config.json`, o hook
PreToolUse do plugin (`scripts/write_gate.py`, matcher `Bash|PowerShell`)
nega o comando de shell de um agente que roda `.kb/kb.py create`, `file`,
`supersede` ou `update`, e a mensagem indica `filing-proposal`,
`semantic-hygiene` e este comando. `proposal-apply` roda o CLI clássico no
próprio subprocesso, que o hook nunca vê. Leituras e os demais comandos
clássicos passam, projetos só clássicos não têm gate, e o `session-hint`
acrescenta uma linha com a regra. O hook orienta agentes; não os autentica. O
Claude Code o roda assim que instalado; o Codex o roda depois que o usuário
confia no hook alterado. O dono do projeto pode desligá-lo com
`{"write_gate": {"enabled": false}}` mesclado na config do vNext.

### `approved-filing`

Propósito: registrar em uma chamada um registro que o usuário aprovou no chat.

Use quando: o usuário viu no chat título, conteúdo, categoria, confiança e lastro do registro e disse sim.

Não use quando: a aprovação vem depois ou de outra pessoa; escreva um `filing-proposal` e rode `proposal-apply` depois do sim.

Exemplo no repositório:

```powershell
$sourceId = 'replace-with-ingested-source-id'
$approver = 'replace-with-approver-id'
python core\versions\kb-wiki-vnext\runtime\kb_next.py approved-filing --category DECISAO --domain operations --title "Use NOW-only startup" --content "Read only .kb-next/memory/NOW.md at session start." --confidence 0.95 --source-id $sourceId --approval-note "Owner approved in chat" --actor $approver --actor-runtime human --json
```

Exemplo stand-alone:

```powershell
$sourceId = 'replace-with-ingested-source-id'
$approver = 'replace-with-approver-id'
python runtime\kb_next.py approved-filing --category FATO --domain research --title "Replace with the approved title" --content "Replace with the approved content." --confidence 0.9 --source-id $sourceId --approval-note "Owner approved in chat" --actor $approver --actor-runtime human --json
```

O lastro segue a regra do `proposal-apply`: `--source-id` nomeia uma fonte registrada com `python .kb/kb.py ingest <path> --json`, `--record-id` um registro existente; os dois se repetem. A confiança precisa atingir o piso do apply (`filing_policy.confidence_bands.high`, padrão 0.8). `--supersedes <id>` substitui um registro ativo e pode trocar a categoria; `--valid-until none` limpa a data que o registro antigo carregava.

Saída esperada: um manifest em `.kb-next/manifests/approved-filing/`, uma linha `approved-filing` em `.kb-next/operations.jsonl` e o registro novo em `.kb/`. Uma chamada bloqueada (lastro ausente ou desconhecido, confiança baixa, alvo de supersede desconhecido ou inativo, ou registro ativo com o mesmo título, que se substitui por supersede) imprime os avisos, não escreve nada e sai com código 1.

### `wiki-synthesis-plan`

Propósito: planejar e opcionalmente escrever drafts machine/human de wiki em `.kb-next/`.

Use quando: preparar conteúdo de wiki revisável a partir de evidência da KB.

Não use quando: você pretende publicar diretamente em `.kb/wiki/live`.

Exemplo no repositório:

```powershell
python core\versions\kb-wiki-vnext\runtime\kb_next.py wiki-synthesis-plan --topic "vnext-architecture" --domain architecture --limit 10 --json
```

Exemplo stand-alone:

```powershell
python runtime\kb_next.py wiki-synthesis-plan --topic "release-operations" --domain operations --limit 10 --json
```

Esses são planos de primeira passagem. Somente depois de revisar os registros
retornados uma segunda passagem deve fornecer
`--judgment @<caminho> --write-drafts`. Os drafts permanecem em `.kb-next/`;
nenhuma passagem publica em `.kb/wiki/live`.

Prompt conversacional:

```text
Crie um wiki synthesis plan e drafts apenas em .kb-next. Não publique páginas live.
```

Saída esperada: plano de síntese, registros de suporte e caminhos opcionais de draft.

Riscos: drafts são derivados e revisáveis; não são publicação canônica.

### `wiki-draft-review`

Propósito: revisar e opcionalmente materializar superfícies de revisão de wiki draft em `.kb-next/`.

Use quando: drafts machine e human existem e precisam de checks de proveniência/confiança antes de decisão de promoção.

Não use quando: registros-fonte são desconhecidos, inativos, superseded ou abaixo do threshold de confiança.

Exemplo no repositório:

```powershell
python core\versions\kb-wiki-vnext\runtime\kb_next.py wiki-draft-review --topic "vnext-architecture" --materialize --json
```

Exemplo stand-alone:

```powershell
python runtime\kb_next.py wiki-draft-review --topic "release-operations" --min-confidence 0.8 --json
```

Prompt conversacional:

```text
Revise os drafts de wiki por proveniência e confiança. Materialize saída de revisão apenas em .kb-next.
```

Saída esperada: status da revisão, warnings/blockers e caminhos opcionais materializados em `.kb-next/`.

Riscos: materialização não é publicação live; não apresente como `.kb/wiki/live`.

### `wiki-draft-status`

Propósito: listar os tópicos de wiki que precisam de drafts vNext, revisão ou atualização.

Use quando: KB + Wiki está ativo e você precisa do backlog de drafts, por
exemplo no fim da sessão. O comando de plugin `vnext-wiki-drafts` parte desta lista.

Não use quando: o workspace opera só com KB; o comando então não retorna
tópicos e traz uma nota para ativar `kb-wiki`.

Exemplo no repositório:

```powershell
python core\versions\kb-wiki-vnext\runtime\kb_next.py wiki-draft-status --json
```

Exemplo stand-alone:

```powershell
python runtime\kb_next.py wiki-draft-status --json
```

Prompt conversacional:

```text
Rode wiki-draft-status e liste os tópicos que precisam de síntese, revisão ou atualização. Ainda não escreva drafts.
```

Saída esperada: `wiki_enabled`, `counts` e uma entrada por tópico (um domínio
com pelo menos `min_records_per_topic` registros ativos) com `state`
(`needs_synthesis`, `needs_review`, `stale` ou `current`) e `next_args` para
`wiki-synthesis-plan` e `wiki-draft-review`.

Riscos: não escreve em `.kb/` nem em `.kb-next/`; drafts ainda exigem
`wiki-synthesis-plan` e `wiki-draft-review`.

## Practical Conversation Patterns / Padrões Práticos De Conversa

Começar fino:

```text
Use a superfície vNext específica do cliente ou o runtime `session-start`. Leia apenas NOW.md. Depois me diga qual contexto extra precisa, se precisar.
```

Perguntar status sem histórico amplo:

```text
Use lookup com facet status para o estado atual do release vNext. Não abra artefatos históricos se lookup for suficiente.
```

Transformar descoberta em proposta:

```text
Prepare um filing-proposal para esta descoberta com fonte e tags. Pare antes de proposal-apply.
```

Revisar HOT overflow:

```text
Rode semantic-hygiene para hot-overflow em modo report-only. Agrupe findings em manter, propor e ignorar.
```

Draft de wiki com segurança:

```text
Rode wiki-synthesis-plan com write-drafts, depois wiki-draft-review. Mantenha tudo em .kb-next.
```

Usar Cowork manualmente:

```text
Como o Cowork pode não rodar hooks nem expor comandos de forma consistente, comece pela ação vNext namespaced exibida pela UI do plugin ou invoque o skill em linguagem natural. Use `session-start` do runtime como fallback e leia apenas NOW.md.
```

## Verification / Verificação

Este guia está atualizado quando todos os comandos do parser do runtime,
incluindo `bootstrap`, aparecem nos guias em inglês e português; a validação de
produto passa; os ZIPs de plugin contêm `runtime/kb_next.py`; e o bundle
stand-alone inclui `products/kb-wiki-vnext/docs/*/usage-guide.md`.

## Troubleshooting / Solução De Problemas

Se um comando falhar porque `.kb/kb.py` está ausente, crie `.kb/` com o
comando `install-classic` do runtime (ele usa o `classic-template/.kb/` do
stand-alone ou o scaffold do kb-lifecycle). Se o runtime vNext estiver ausente,
resolva o runtime do plugin ou artefato stand-alone e rode `bootstrap`; não peça
ao usuário para posicionar o arquivo manualmente. Se um comando pedir
julgamento, prefira `--judgment @path` depois de revisar os candidatos da
primeira passagem. Se um fluxo puder alterar registros em `.kb/kb.db`, pare,
exceto quando a operação for um `proposal-apply` aprovado. O `wiki-sync`
clássico rodado pela ativação `kb-wiki` e o `install-classic` também escrevem
em `kb.db`; isso é esperado.

## Related / Relacionados

- [Manual do usuário](user-manual.md)
- [Referência de comandos do plugin](command-reference.md)
- [Arquitetura](architecture.md)
- [Troubleshooting](troubleshooting.md)
