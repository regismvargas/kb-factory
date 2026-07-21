# Guia De Uso KB/Wiki vNext

## Purpose / Propósito

Explicar como usar cada comando do runtime KB/Wiki vNext em projetos reais e em conversas com agentes.

## Audience / Público

Usuários, admins e maintainers que precisam ir além da instalação: quando usar cada feature, o que pedir ao agente e como evitar mudanças acidentais na memória canônica.

## Prerequisites / Pré-requisitos

- KB/Wiki vNext `0.3.0` instalado por ZIP de plugin ou bundle stand-alone.
- Identidade registrada pelo maintainer: release, KB Lifecycle, vNext e
  runtime `0.3.0`; Session Gate `0.2.7`. O marketplace não tem autoridade de
  versão; os manifestos dos plugins definem a identidade de update.
- Workspace com `.kb/` disponível como memória canônica.
- Python disponível como `python`.
- Acordo de que `.kb-next/` é memória operacional, evidência de proposta e materialização de drafts, não fonte canônica.

## Mental Model / Modelo Mental

`.kb/` permanece canônico. Ele guarda a memória durável do projeto e é a única camada que deve ser tratada como fonte de verdade. KB/Wiki vNext lê `.kb/` por caminhos suportados do runtime, e apenas `proposal-apply` pode levar uma proposta aprovada de volta para `.kb/` por meio de `.kb/kb.py`.

`.kb-next/` é a camada de trabalho. Ela guarda decisões de ativação, pistas de sessão, propostas semânticas, manifests de inferência, drafts de wiki, superfícies materializadas de revisão, exports de adapters e evidência operacional. Ela existe para ajudar agentes a trabalhar com contexto fino e revisável, sem carregar todo o histórico por padrão.

Comandos descritos como read-only são read-only contra o `.kb/` canônico. Comandos como `session-start` e `lookup` ainda fazem append de evidência operacional em `.kb-next/operations.jsonl`.

Resumo de mutações:

| Família de comandos | `.kb/` | `.kb-next/` |
|---|---|---|
| `bootstrap` | sem mudança | instala apenas `runtime/kb_next.py` |
| `compliance-preflight`, `source-linkage-audit`, `semantic-hygiene` padrão | read-only | sem escrita |
| `session-start`, `lookup` | read-only | append de evidência operacional |
| ativação, semântica, propostas, export e wiki | read-only, salvo indicação abaixo | escreve config, manifests, propostas, drafts, exports ou evidência operacional governada |
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

1. Garanta que `.kb/` existe a partir do template clássico do bundle ou de um workspace KB Factory existente.
2. Rode `activation-wizard`.
3. Rode `python runtime/kb_next.py --project-root <workspace> session-start`.
4. Use `lookup` primeiro; use comandos semânticos apenas quando houver julgamento LLM fornecido ou revisável.

Projeto existente:

1. Rode `python runtime/kb_next.py --project-root <workspace> session-start`.
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
4. Aplique somente com `proposal-apply --approve --approval-note`.

Trabalho de draft de wiki:

1. Use `wiki-synthesis-plan --write-drafts`.
2. Revise drafts machine e human.
3. Use `wiki-draft-review --materialize` apenas para materialização de revisão em `.kb-next/`.
4. Não publique em `.kb/wiki/live` como parte do vNext.

Upgrade e rollback:

1. Registre pacote/runtime atual.
2. Instale o novo plugin ou descompacte o bundle stand-alone ao lado do anterior.
3. Faça bootstrap a partir do novo artefato e rode `python runtime/kb_next.py --project-root <workspace> session-start`,
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

Riscos: escolher KB + Wiki sem aprovação pode implicar um fluxo de wiki mais amplo do que o projeto autorizou.

### `session-start`

Propósito: emitir o contrato fino de startup para a conversa atual.

Basename lógico distribuído: `vnext-session-start`. Invocação no Claude Code:
`/kb-wiki-vnext:vnext-session-start`. Superfície no Codex: skill embutido.
Subcomando do runtime: `session-start`.

Use quando: iniciar toda sessão com agente.

Não use quando: você está tentando aplicar mudanças na memória canônica. Ele não escreve em `.kb/`, mas faz append da evidência de sessão em `.kb-next/operations.jsonl`.

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

Saída esperada: registros encontrados com `classic_kb_mode` read-only.

Riscos: termos fracos podem perder registros relevantes; tente outro lookup antes de escanear arquivos.

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

Prompt conversacional:

```text
Revise HOT overflow primeiro em modo report-only. Se houver candidatos claros, proponha mudanças, mas não aplique.
```

Saída esperada: findings report-only ou IDs de proposta quando `--write-proposals` for usado.

Riscos: escrever propostas ainda não aplica nada, mas cria artefatos de revisão que precisam triagem.

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

Riscos: memória com baixa proveniência deve ser bloqueada ou ficar como evidência draft.

### `proposal-apply`

Propósito: aplicar uma proposta aprovada por meio de `.kb/kb.py`.

Use quando: uma pessoa revisou a proposta e aprovou explicitamente a mutação canônica.

Não use quando: aprovação está ausente, ambígua ou a proposta está fora de `.kb-next/proposals`.

Exemplo no repositório:

```powershell
$proposalId = 'replace-with-reviewed-proposal-id'
python core\versions\kb-wiki-vnext\runtime\kb_next.py proposal-apply --proposal $proposalId --approve --approval-note "Approved by project owner after proposal review" --json
```

Exemplo stand-alone:

```powershell
$proposalPath = '.kb-next\proposals\replace-with-reviewed-proposal.json'
python runtime\kb_next.py proposal-apply --proposal $proposalPath --approve --approval-note "Maintainer approved after review" --json
```

Substitua o valor da variável de exemplo pela proposta revisada retornada pelo comando
anterior. Nunca infira um ID nem reutilize uma nota de aprovação da documentação.

Prompt conversacional:

```text
Aplique esta proposta apenas se ela estiver vinculada a um manifest válido e eu a tiver aprovado explicitamente nesta mensagem.
```

Saída esperada: status applied/blocked e detalhes da ponte canônica.

Riscos: este é o único comando do fluxo destinado a mutar memória canônica; use deliberadamente.

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

Se um comando falhar porque `.kb/kb.py` está ausente, faça bootstrap de `.kb/`
pelo `classic-template/.kb/` do stand-alone. Se o runtime vNext estiver ausente,
resolva o runtime do plugin ou artefato stand-alone e rode `bootstrap`; não peça
ao usuário para posicionar o arquivo manualmente. Se um comando pedir
julgamento, prefira `--judgment @path` depois de revisar os candidatos da
primeira passagem. Se um fluxo puder alterar `.kb/kb.db`, pare, exceto quando a
operação for um `proposal-apply` aprovado.

## Leituras de grafo

Use o namespace `graph` para inspeção estrutural determinística sem escrever
em `.kb/` ou `.kb-next`:

```powershell
python .\.kb-next\runtime\kb_next.py --project-root . graph backlinks KB-ID --json
python .\.kb-next\runtime\kb_next.py --project-root . graph lineage KB-ID --json
python .\.kb-next\runtime\kb_next.py --project-root . graph neighbors KB-ID --json
python .\.kb-next\runtime\kb_next.py --project-root . graph source-records SRC-ID --json
python .\.kb-next\runtime\kb_next.py --project-root . graph verify --json
python .\.kb-next\runtime\kb_next.py --project-root . graph source-backfill --limit 3 --json
```

Trate as linhas de backfill como propostas. Aplique um par aceito apenas pelo
comando clássico `graph source-link`, com evidência de actor.

## Related / Relacionados

- [Manual do usuário](user-manual.md)
- [Referência de comandos do plugin](command-reference.md)
- [Arquitetura](architecture.md)
- [Troubleshooting](troubleshooting.md)
