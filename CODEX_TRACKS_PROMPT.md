# Prompt para Codex - Executar Tracks do Conductor sem plugin nativo

> Copie o bloco da secao "Prompt base" e cole no Codex no inicio da sessao.
> Troque apenas os campos da track e da tarefa da sessao.

---

## Como pensar esse fluxo no Codex

O Codex nao tem o plugin nativo do Conductor aqui. Entao ele precisa operar no modo manual:

- ler os arquivos de contexto do repositorio
- ler os arquivos da track
- executar as tasks em ordem
- atualizar os arquivos do `conductor/` manualmente
- usar `metadata.json` como fonte principal de progresso

### Fonte de verdade recomendada

Se houver divergencia entre arquivos, use esta prioridade:

1. `conductor/tracks/<track-id>/metadata.json`
2. checkboxes de `conductor/tracks/<track-id>/plan.md`
3. `conductor/tracks/<track-id>/index.md`
4. `conductor/tracks.md`

Observacao: neste repositorio, ja existe historico de `index.md` e status globais ficarem defasados. O Codex deve reconciliar isso, nao assumir que tudo ja esta sincronizado.

### Regras importantes para o Codex

- Nao falar como se tivesse executado comandos do plugin do Conductor.
- Nao inventar automacoes ocultas.
- Nao pular tasks do `plan.md`.
- Nao ampliar o escopo sem necessidade.
- Ler os arquivos que vao ser alterados antes de editar.
- Atualizar os artefatos do Conductor a cada task concluida.
- Fazer commit ao final de cada fase, nao a cada task.

---

## Prompt base

```text
Voce esta trabalhando no repositorio `agentic-workflow-medallion-pipeline`.
Voce NAO tem plugin nativo do Conductor nesta sessao. Portanto, opere manualmente editando os arquivos em `conductor/`.

## Objetivo operacional

Executar a track abaixo seguindo o padrao do Conductor, mantendo os arquivos da track consistentes durante a implementacao.

Track alvo:
- Track ID: {TRACK_ID}
- Titulo: {TRACK_TITLE}

## Contexto inicial obrigatorio

Antes de implementar qualquer coisa, leia nesta ordem:

1. `CLAUDE.md`
2. `CODEX_MANUAL.md`
3. `conductor/workflow.md`
4. `conductor/tracks.md`
5. `conductor/tracks/{TRACK_ID}/metadata.json`
6. `conductor/tracks/{TRACK_ID}/spec.md`
7. `conductor/tracks/{TRACK_ID}/plan.md`
8. `conductor/tracks/{TRACK_ID}/index.md` se existir

Depois leia os arquivos de codigo citados no `plan.md` antes de editar.

## Como tratar o Conductor sem plugin

Voce deve usar os arquivos da track como o proprio sistema de controle:

- `metadata.json`: fonte principal do estado atual
- `spec.md`: o que deve ser entregue
- `plan.md`: ordem de execucao e checklist
- `index.md`: resumo legivel da track
- `conductor/tracks.md`: registro global da track

Se encontrar divergencia entre esses arquivos:

- trate `metadata.json` e os checkboxes do `plan.md` como fonte principal
- corrija `index.md` e `conductor/tracks.md` para refletirem a realidade
- mencione brevemente na resposta que houve reconciliacao de estado

## Regras de execucao

1. Execute uma task por vez, sempre na ordem do `plan.md`.
2. Antes de cada task, leia os arquivos que serao alterados.
3. Implemente apenas o que a task pede, sem expandir escopo.
4. Siga as convencoes do projeto em `CLAUDE.md` e `CODEX_MANUAL.md`.
5. Para notebooks Databricks:
   - manter formato `.py` de notebook Databricks
   - header markdown na primeira celula
   - `# DBTITLE` em toda celula de codigo
   - imports no topo
   - comentarios em pt-BR
   - nunca colocar `dbutils.notebook.exit()` dentro de `try/except`
6. Nunca hardcode secrets, tokens, account IDs ou configuracoes sensiveis.
7. Use `pipeline_lib`, nunca `lib`, nos imports Python do projeto.
8. Se a task pedir algo que conflite com o codigo existente, adapte a implementacao ao repositorio real e registre a decisao.

## Loop obrigatorio apos cada task concluida

Ao concluir uma task do `plan.md`, faca imediatamente:

1. Marque a task como `[x]` no `plan.md`
2. Atualize `metadata.json`:
   - `status`: `in_progress` ou `complete`
   - `updated`: data atual
   - `current_phase`
   - `current_task`
   - `phases.completed`
   - `tasks.completed`
3. Atualize `index.md`:
   - status textual
   - contagem de fases
   - contagem de tasks
4. Se a fase terminou:
   - faca verificacao da fase
   - crie um commit com conventional commit em pt-BR

## Encerramento obrigatorio da track

Quando todas as tasks estiverem concluidas:

1. Atualize `metadata.json` para:
   - `status: "complete"`
   - `phases.completed = phases.total`
   - `tasks.completed = tasks.total`
2. Atualize `conductor/tracks.md` marcando a linha da track com `[x]`
3. Atualize a data `Updated` da linha da track
4. Garanta que `index.md` reflita o estado final
5. Resuma o que foi entregue e quais verificacoes foram executadas

## Verificacao e testes

A validacao deve ser proporcional ao tipo de mudanca:

- Mudancas em `observer-framework/observer/`: rodar `ruff check observer-framework/observer/` e `pytest observer-framework/tests/`
- Mudancas em `pipelines/pipeline-seguradora-whatsapp/pipeline_lib/`: rodar `ruff check pipelines/pipeline-seguradora-whatsapp/pipeline_lib/` e `pytest pipelines/pipeline-seguradora-whatsapp/tests/`
- Mudancas em notebooks/scripts de deploy: rodar os testes ou checks que fizerem sentido para os arquivos alterados
- Mudancas apenas de documentacao/conductor: nao inventar testes, apenas informe que nao houve execucao de testes

Se existir uma etapa explicita de verificacao no `plan.md`, ela tem prioridade.

## Estilo de resposta

- Comece dizendo qual track e qual task voce vai executar agora.
- Ao longo da sessao, deixe claro quando concluiu uma task e quando atualizou os arquivos do Conductor.
- Se estiver retomando trabalho, diga de qual ponto voce retomou com base em `metadata.json`.
- Se houver bloqueio real, descreva o bloqueio concreto e a menor proxima acao necessaria.
- Nao diga que usou comandos do plugin do Conductor.

## Tarefa desta sessao

Execute a track `{TRACK_ID}` ({TRACK_TITLE}).

Ponto de partida desta sessao:
{SESSION_GOAL}

Comece lendo os arquivos obrigatorios, identifique a proxima task pendente a partir de `metadata.json` + `plan.md`, e siga em frente.
```

---

## Exemplos prontos

### Iniciar uma track do zero

Use este valor em `SESSION_GOAL`:

```text
Comecar do zero. Assuma que a track esta pendente e valide o estado real antes de implementar.
```

### Continuar uma track interrompida

Use este valor em `SESSION_GOAL`:

```text
Retomar do ponto atual. Leia `metadata.json` e os checkboxes do `plan.md`, reconcilie qualquer divergencia e continue da primeira task pendente.
```

### Revisar progresso sem implementar

Se voce quiser apenas uma auditoria da track:

```text
Nao implemente nada ainda. Leia os arquivos da track, identifique o estado real, liste tasks concluidas, tasks pendentes, inconsistencias de status e a proxima task recomendada.
```

---

## Exemplo preenchido

```text
Voce esta trabalhando no repositorio `agentic-workflow-medallion-pipeline`.
Voce NAO tem plugin nativo do Conductor nesta sessao. Portanto, opere manualmente editando os arquivos em `conductor/`.

Track alvo:
- Track ID: observer-trigger_20260409
- Titulo: Observer - Trigger Automatico

Antes de implementar qualquer coisa, leia nesta ordem:
1. `CLAUDE.md`
2. `CODEX_MANUAL.md`
3. `conductor/workflow.md`
4. `conductor/tracks.md`
5. `conductor/tracks/observer-trigger_20260409/metadata.json`
6. `conductor/tracks/observer-trigger_20260409/spec.md`
7. `conductor/tracks/observer-trigger_20260409/plan.md`
8. `conductor/tracks/observer-trigger_20260409/index.md`

Retomar do ponto atual. Leia `metadata.json` e os checkboxes do `plan.md`, reconcilie qualquer divergencia e continue da primeira task pendente.
```

---

## Dica pratica

Para Codex, o melhor fluxo neste repositorio e:

1. uma track por sessao
2. um commit por fase
3. `metadata.json` como fonte de verdade
4. reconciliar `index.md` e `tracks.md` quando estiverem atrasados

Se quiser, na proxima mensagem eu tambem posso te entregar uma versao ainda mais curta, pronta para colar, focada em uma track especifica como `observer-trigger_20260409`.
