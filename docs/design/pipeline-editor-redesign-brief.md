# Brief: Redesign do Pipeline Editor (V2)

> Documento para alimentar **Claude Design**. Quero output em wireframes + componentes Vue 3 + @nuxt/ui, mantendo o contrato técnico abaixo intacto. O backend está em produção; a UI nova precisa se encaixar nos endpoints e DSL existentes.

---

## 1. Contexto do Produto

**Flowertex** é uma plataforma de "pipeline agent" — usuário sobe templates de pipeline (one-click deploy) e depois conversa com a plataforma para modificar transformações sem mexer em código Databricks/Spark. O **Pipeline Editor** é a feature onde a conversa vira mudança real: o usuário descreve em linguagem natural ("renomeie X para Y"), a plataforma propõe um draft estruturado, executa preview no Databricks com namespace tenant-scoped, e abre uma Pull Request no GitHub com o diff PySpark gerado.

**Hoje (V1):**
- Restrição: só **camada Silver** (Bronze e Gold ficam fora).
- 11 operações DSL suportadas: `drop_column`, `rename_column`, `cast_column`, `trim`, `regex_replace`, `coalesce`, `derive_column`, `filter_rows`, `date_format`, `json_extract`, `mask_pii`.
- Fluxo: NL message → proposta estruturada → preview SQL → aprovação humana → PR no repo Git.
- Restrição Silver é hardcoded em 4 camadas do backend — **não inventar UI para outras camadas**.

---

## 2. Stack & Brand

- **Framework**: Nuxt 4.4.2 + Vue 3 + TypeScript
- **UI lib**: `@nuxt/ui` (Tailwind sob o capô)
- **Estado**: Pinia
- **Composables**: `@vueuse/nuxt`
- **Estrutura**: Atomic Design — `atoms/` → `molecules/` → `organisms/` → `templates/`
- **Marca**: Flowertex / "Pipeline agent platform" — header com logo + sidebar com Chat, Market, Deploys, Canais
- **Tom visual**: clean, neutro, foco em conteúdo (telas têm muito dado tabular)
- Consistência com `/chat`, `/deployments`, `/marketplace` (mesma sidebar, mesma navegação superior)

---

## 3. V1: Estado Atual em Uma Frase

Workspace de uma única rota (`/pipelines/{id}`) com 5 abas (Overview, Editar, Dados, Diagrama, Histórico). A aba **Editar** é grid 2-col: coluna esquerda tem chat NL + ProposalDiffPanel; coluna direita empilha TransformBuilder (low-code) + DataPreviewGrid + ApprovalTimeline + bloco prompt.md.

**Screenshots V1**: ver pasta `.playwright-mcp/` no repositório (capturadas durante validação E2E).
- `01-after-login.png` — landing /chat
- `02-workspace-before-send.png` — workspace antes da mensagem
- `03-proposta-gerada.png` — proposta estruturada renderizada
- `04-preview-ready.png` — preview com schema_delta
- `05-historico-sessions.png` — aba Histórico

---

## 4. Problemas Observados na V1 (drivers do redesign)

1. **Densidade visual**: grid 2-col satura em laptop 14". Tudo fica acima da dobra mas nada respira.
2. **Timeline passiva**: o `ApprovalTimeline` mostra 5 estados (Draft → Preview → prompt.md → Aprovação → Reversão) mas não comunica bloqueios — quando `approve` falhou na validação E2E por bug do marker, o erro 500 só apareceu no DevTools console.
3. **Conversa não persiste visualmente**: backend salva `PipelineEditMessage` (role user/assistant) com histórico completo, mas a UI só mostra a última proposta — usuário perde contexto entre iterações.
4. **Modos misturados**: chat NL e builder low-code ocupam a mesma tela sem deixar claro qual está "ativo" / "fonte de verdade" naquele momento. Quem edita: o LLM ou o usuário?
5. **Sessões opacas**: Pinia mantém `activeEditSessionId`, mas usuário não vê em qual sessão está mexendo. Bug observado: smoke test criou sessão prévia e a UI a reaproveitou silenciosamente, fazendo approve em sessão diferente da que tinha a proposta.
6. **Approve sem confirmação**: botão "Aprovar e abrir PR" cria PR real no GitHub sem modal de confirmação. Risco de PR acidental persistente.
7. **Sem skeleton/feedback durante preview**: preview no Databricks demora 30-60s; UI fica congelada com loading sutil.
8. **Erro handling fraco**: erros aparecem como toast efêmero ou só em console — sem banner contextual com ação retry.

---

## 5. Personas

| Persona | Goals | Frustrações na V1 |
|---|---|---|
| **Data Engineer (Rodrigo)** — dono do pipeline, sabe PySpark, faz a maioria das edições | Iterar rápido em transformações Silver, validar no Databricks antes de PR, manter histórico auditável | Sessões ambíguas, falta de preview comparativo, prompt.md "escondido" |
| **Analyst** — consome dados, pede mudanças mas não conhece Spark | Descrever em NL "renomeie X pra Y" sem precisar conhecer DSL | Sem onboarding/zero state, builder low-code intimida |
| **Ops / Tech Lead** — revisa e aprova PRs, monitora produção | Ver o que vai mudar no diff antes de aprovar, entender risco, reverter rápido | Aprovação sem confirmação, sem resumo claro do PR |

---

## 6. Jornadas-alvo

| ID | Jornada | Crítico que funcione |
|---|---|---|
| J1 | NL puro: digita pedido → revisa proposta → preview → aprova | Maior caso de uso. Precisa ser rápido e óbvio. |
| J2 | Low-code (sem NL): escolhe nó + operação no builder → preview → aprova | Backup quando NL falha ou para precisão fina |
| J3 | Híbrido: gera por NL → ajusta detalhes no builder → preview → aprova | Comum em iterações refinadas |
| J4 | Revisão antes de aprovar: lê diff de schema + diff de código + risk_score + test_plan | Driver de confiança pro Ops |
| J5 | Compartilhar sessão read-only: gera share-token, copia URL, manda pra stakeholder não-logado | Bom pra demos / aprovação assíncrona |
| J6 | Reverter PR aberta por engano: encontra a sessão, clica revert, confirma | Recuperação de erro |

Jornadas **fora deste redesign**: criação de pipelines novos (vive em `/marketplace`), gestão de deploys (vive em `/deployments`).

---

## 7. Requisitos Funcionais (MUST)

Numerados para rastrear cobertura:

**RF-01** Topo do workspace mostra sempre: nome do pipeline, **camada ativa** (Silver), **nó alvo** selecionado, **tabela alvo**, badge do modo ativo (Chat / Builder / Híbrido) e da sessão (status + ID curto).

**RF-02** Histórico de mensagens NL persistente em formato chat (avatares user/assistant + timestamp), scrollável, com a proposta estruturada renderizada inline depois de cada resposta do assistant.

**RF-03** Botão "Nova sessão" sempre visível — usuário precisa conseguir criar sessão limpa sem ter que mexer em estado anterior. Sessões existentes ficam em painel lateral colapsável (com status: draft, pr_created, validated).

**RF-04** TransformBuilder (low-code) inclusivo: cada operação é um card editável (op type + parâmetros conforme schema). Botão "Adicionar operação" com seletor das 11 ops. Operações reordenáveis (drag&drop).

**RF-05** Painel de proposta exibe: explanation textual, risk_score como gauge (0-10), files_affected como chips clicáveis, test_plan como checklist.

**RF-06** Preview tem dois modos: **schema diff** (3 colunas: Removidas / Renomeadas / Derivadas) e **dados diff** (tabela side-by-side rows_before vs rows_after, primeiras 50 linhas). Switch entre os dois sem refetch.

**RF-07** Estados explícitos do fluxo, sempre visíveis: `idle`, `generating_proposal` (LLM rodando), `running_preview` (Databricks), `validating` (codegen + ruff), `opening_pr` (GitHub API), `pr_created`, `validation_failed`, `error`. Cada estado tem ícone + texto + ação possível.

**RF-08** **Bloquear** "Aprovar e abrir PR" se: preview não rodou OU preview status != "ready" OU validação rejeitou. Botão fica disabled com tooltip explicando o bloqueio.

**RF-09** Modal de confirmação antes do approve real, com resumo: branch name proposto (`pipeline-editor/{session_short_id}`), base ref (`dev`), lista de arquivos afetados, total +/-, link "Cancelar" e "Confirmar e abrir PR".

**RF-10** Zero state na primeira edição: ilustração + texto curto explicando "Descreva uma mudança na Silver ou use o builder low-code" + 3 exemplos clicáveis ("renomear coluna", "remover coluna sensível", "filtrar linhas").

**RF-11** Erro handling: banner contextual no topo do workspace (não toast) com mensagem, código (se HTTP), ação primária (Retry / Ver detalhes). Console DevTools não pode ser a única fonte de feedback.

**RF-12** Botão "Compartilhar" (share-token) gera URL pública read-only, copia para clipboard, mostra preview de como o stakeholder verá. Suporta expiração configurável (default 7 dias).

**RF-13** Tela `/shared/pipeline-edit/{token}` — versão read-only do workspace: sem chat, sem builder, só visualização da proposta + preview + diff. Sem login.

**RF-14** Botão "Reverter PR" disponível em sessões com `status == "pr_created"`. Modal de confirmação. Chama endpoint `/revert` com `mode: "revert_pr"`.

**RF-15** Aba "Histórico" lista sessões da pipeline com: título, status, autor, data, link rápido pro PR (se houver), botão "Continuar editando".

---

## 8. Requisitos Não-funcionais

- **NF-01** Responsivo do **desktop pra cima** (>1024px). Mobile pode ser explicitamente "não suportado nesta release" com banner de aviso.
- **NF-02** WCAG **AA**: contraste mínimo, foco visível em todos os interativos, ARIA labels para ícones-only.
- **NF-03** Atalhos teclado: `Ctrl+Enter` envia mensagem NL, `Esc` cancela modal, `Ctrl+S` salva draft do builder, `?` abre cheatsheet de atalhos.
- **NF-04** Skeleton/placeholder durante operações > 500ms (NL, preview, validação). Spinners só pra micro-ações.
- **NF-05** Dark mode opcional (consistente com /chat se já existir).
- **NF-06** Latência percebida: preview pode levar até 60s — mostrar progresso e timeout claro (sem "loading infinito").
- **NF-07** Auto-save do draft no builder a cada mudança (debounce 1s) — perda de trabalho é inaceitável.

---

## 9. Contrato Técnico Imutável

> Não alterar. O backend está em produção; alterações invalidam a feature.

### 9.1 Restrição

- **Silver only**. Hardcoded no schema Pydantic (`schemas.py:82-88`), manifest (`manifest.py`), agent (`nl_agent.py`), e route guard (`pipeline_editor.py:183-195`).
- **Pipelines**: a UI deve aceitar qualquer manifest com nós Silver. Hoje só `pipeline-seguradora-whatsapp` existe, mas estrutura suporta N templates.

### 9.2 DSL — 11 operações + parâmetros

Todas as ops vão num array `operations: [{op, ...params}]`. Campos obrigatórios conforme `op`:

| `op` | Campos obrigatórios | Campos opcionais |
|---|---|---|
| `drop_column` | `column` | — |
| `rename_column` | `column`, `new_name` | — |
| `cast_column` | `column`, `data_type` | — |
| `trim` | `column` | — |
| `regex_replace` | `column`, `pattern`, `replacement` | — |
| `coalesce` | `column` | `source_columns: string[]` |
| `derive_column` | `column`, `expression` (SQL Spark, sem `F.col`) | — |
| `filter_rows` | `expression` (SQL Spark) | — |
| `date_format` | `column`, `format` | — |
| `json_extract` | `column`, `json_path`, `new_name` | — |
| `mask_pii` | `column` | — |

### 9.3 Endpoints da API (`/api/v1/pipelines/{id}`)

| Método | Path | Auth | Descrição |
|---|---|---|---|
| GET | `/` | `chat` | Workspace + manifest filtrado por silver |
| GET | `/edit-sessions` | `chat` | Lista sessões |
| POST | `/edit-sessions` | `chat` | Cria sessão (`{title, target_layers:["silver"], base_ref:"dev"}`) |
| POST | `/edit-sessions/{sid}/messages` | `chat` | Envia mensagem NL + draft opcional → `EditProposal` |
| PUT | `/edit-sessions/{sid}/draft` | `chat` | Atualiza draft manual (builder low-code) |
| POST | `/edit-sessions/{sid}/preview` | `chat` | Roda preview SQL no Databricks (`{sample_rows: int}`) |
| POST | `/edit-sessions/{sid}/export` | `chat` | Exporta resultado preview (`{format: "csv"\|"parquet"}`) |
| GET | `/edit-sessions/{sid}/exports/latest.{csv\|parquet}` | `chat` | Download arquivo preview |
| GET | `/edit-sessions/{sid}/prompt.md` | `chat` | Markdown auditável para LLM externo |
| POST | `/edit-sessions/{sid}/share` | `chat` | Cria share-token público |
| POST | `/edit-sessions/{sid}/approve` | `create_pr` | Aprova → codegen → validate → PR (`{create_pr: bool}`) |
| POST | `/edit-sessions/{sid}/revert` | `create_pr` | Reverte (`{mode: "draft"\|"revert_pr"\|"close_pr"}`) |

Endpoint público (sem auth): `GET /api/v1/shared/pipeline-edit/{token}` — resolve sessão read-only.

### 9.4 Modelos de domínio

```
PipelineEditSession
├─ id, pipeline_id, company_id, created_by_user_id, title
├─ status: "draft" | "pr_created" | "validated"
├─ target_layers: ["silver"]  // sempre
├─ base_ref: "dev"  // branch de base do PR
├─ draft_branch: string | null
└─ current_version_id: uuid | null

PipelineEditVersion (snapshot iterativo)
├─ id, session_id, version_number
├─ draft: TransformDraft (DSL)
├─ generated_files: {path: code}
├─ validation_result: {valid, checks[], errors[]}
├─ preview_result: {status, rows_before[], rows_after[], schema_delta, namespace}
└─ pr_metadata: {pr_number, pr_url, branch, state}

PipelineEditMessage (chat)
├─ id, session_id, role: "user" | "assistant"
├─ content: string
├─ tool_events: jsonb
└─ structured_state: jsonb  // proposta serializada quando assistant

PipelineEditArtifact (outputs)
├─ id, session_id, version_id
├─ artifact_type: "preview" | "export:csv" | "export:parquet"
├─ name, content, storage_uri
└─ download_url

PipelineShare (link público)
├─ id, session_id, share_token (urlsafe 32), role: "viewer"
├─ expires_at, is_active
```

### 9.5 Estrutura `EditProposal` (retorno do `/messages`)

```typescript
{
  explanation: string             // texto do LLM
  draft: TransformDraft           // novo draft estruturado
  files_affected: string[]        // paths dos arquivos que vão mudar
  risk_score: number              // 0-10
  test_plan: string[]             // checklist sugerido
}
```

---

## 10. Fora de Escopo (não desenhar)

- Bronze e Gold (futuro, depende de novo backend)
- Criação/deploy de novos pipelines (já vive em `/marketplace`)
- Editor SQL livre (vetado por segurança — só DSL declarativo)
- Edição multi-user em tempo real (sem CRDTs no backend)
- Visualização de logs de execução do Databricks (vive em `/deployments`)
- Onboarding/tutorial fullscreen (Zero state inline já cobre)

---

## 11. Deliverables Esperados de Claude Design

1. **Wireframes de baixa fidelidade** das 5-7 telas principais (workspace edit, modal approve, share modal, shared read-only, histórico expandido, erro state, zero state)
2. **Wireframes de média fidelidade** com hierarquia visual, espaçamento, componentes finais
3. **Fluxos de navegação** (state diagram) cobrindo J1-J6
4. **Especificação de componentes novos** (se houver) — props, slots, eventos — para encaixar no Atomic Design
5. **Mapping V1 → V2**: tabela de quais organisms da V1 morrem, quais sobrevivem, quais nascem
6. **Código Vue 3 + @nuxt/ui (opcional, bônus)** dos componentes principais, pronto pra integrar
7. **Lista de design tokens** novos necessários (se houver) — cores de estado, espaçamentos, tipos
8. **Acessibilidade checklist**: confirmar que NF-02 está coberto

Critério de "pronto": qualquer dev frontend consegue implementar o redesign lendo só os deliverables acima + o contrato técnico desta brief, sem perguntar mais nada.

---

## 12. Apêndices

### 12.1 V1: rotas Nuxt envolvidas

- `/pipelines/{id}` (logado) — workspace 5 abas
- `/shared/pipeline-edit/{token}` (público) — read-only

### 12.2 V1: organisms existentes (avaliar reuso ou aposentadoria)

`PipelineEditorWorkspace.vue`, `TransformBuilder.vue`, `ProposalDiffPanel.vue`, `DataPreviewGrid.vue`, `PipelineDiagram.vue`, `ApprovalTimeline.vue`, `PreviewExportMenu.vue`.

### 12.3 Glossário

- **Draft**: snapshot da intenção de transformação (DSL declarativo), versionado por sessão.
- **Manifest**: descrição estática do pipeline — nós, arquivos, tabelas, operações suportadas.
- **Insertion marker**: comentário PySpark (`# DBTITLE 1,...`) que marca onde o codegen injeta o bloco low-code.
- **Namespace de preview**: namespace temp no Databricks (`preview_<cpy8>_<pip8>_<ses8>`) onde a query AFTER roda isolada por tenant/pipeline/sessão.
- **Share token**: string urlsafe de 32 bytes que dá acesso público read-only a uma sessão.

### 12.4 Constraints de cor/marca

- Primária Flowertex (procurar nos componentes existentes via `tailwind.config.ts` / @nuxt/ui theme).
- Estados: success (verde), warning (amarelo), error (vermelho), info (azul/neutro). Usar paleta do @nuxt/ui.
- Dark mode: opcional nesta release, mas tokens devem suportar.

---

> Fim do brief. Ao gerar o redesign, **sempre** cite qual RF você está cobrindo em cada decisão. Qualquer divergência do contrato técnico (seção 9) precisa de aprovação explícita do dono do produto antes de virar implementação.
