# Specification: Platform — One-click Deploy Marketplace

**Track ID:** platform-oneclick-deploy_20260410
**Type:** Feature
**Created:** 2026-04-10
**Status:** Draft

## Summary

Adicionar a camada de marketplace + deploy wizard ao shell da plataforma Namastex. O usuario vai poder explorar templates de pipelines (WhatsApp seguros, CRM SAP, E-commerce Hotmart), configurar env vars, disparar um deploy (mock) e acompanhar o progresso em tempo real (mock SSE). Reaproveita integralmente os tokens Namastex da Track A e os atoms/molecules da Track B. Tudo com mocks — o backend real (Celery + Terraform programatico + Databricks SDK) sera uma track separada.

## User Story

Como Rodrigo (admin de uma empresa usuaria da plataforma), quero entrar na area de Marketplace, escolher o template `pipeline-seguradora-whatsapp`, preencher minhas credenciais AWS/Databricks/secrets via um wizard em passos, clicar em "Deploy" e ver em tempo real cada etapa da saga (create S3 bucket, provision Databricks cluster, upload notebooks, trigger first run) ate o pipeline ficar ativo na minha lista de workflows.

## Acceptance Criteria

### Marketplace

- [ ] Pagina `/marketplace` com grid de `TemplateCard`s (minimo 3 templates mockados)
- [ ] Cada card tem: logo/icone, nome, descricao curta, tags (`whatsapp`, `seguros`, `etl`), versao, numero de deploys
- [ ] Busca por nome/tag no topo da pagina
- [ ] Filtro por categoria (ETL, CRM, E-commerce, Analytics)
- [ ] Pagina `/marketplace/[slug]` mostra detalhes do template: descricao longa, architecture diagram placeholder, changelog, dependencies, "Deploy" CTA

### Deploy Wizard

- [ ] Pagina `/deploy/[slug]` com wizard multi-step:
  - **Step 1 — Basics**: nome do deployment, ambiente (dev/staging/prod), tags
  - **Step 2 — Credentials**: AWS account, Databricks workspace URL + token, secrets (anthropic, github)
  - **Step 3 — Configuration**: env vars especificas do template (S3 bucket name, catalog name, schedule cron)
  - **Step 4 — Review**: resumo de tudo + checkbox de confirmacao
  - **Deploy button** dispara a saga mock
- [ ] Validacao de formulario por step (nao avanca sem campos obrigatorios)
- [ ] StepIndicator visual mostrando passo atual

### Deployment Progress

- [ ] Apos clicar "Deploy", redireciona para `/deployments/[id]` com live view
- [ ] Lista de etapas da saga (com icones e status por step):
  1. Validate credentials
  2. Create AWS S3 bucket + IAM role
  3. Provision Databricks secrets scope
  4. Upload pipeline notebooks
  5. Create Databricks workflow
  6. Trigger first run
  7. Register in platform
- [ ] Cada step passa por `pending → running → success/failed` simulado com `setTimeout` (2-4s cada)
- [ ] Log stream ao vivo (`LogLine` components) aparecendo conforme a saga roda
- [ ] Barra de progresso top com percentual
- [ ] Ao final: badge de status + CTA "Abrir chat deste pipeline" que navega para `/chat` com o pipeline novo selecionado

### Deployments History

- [ ] Pagina `/deployments` lista todos os deployments (pending, running, success, failed)
- [ ] Cada item mostra: nome, template, ambiente, status, duracao, timestamp
- [ ] Clicar abre `/deployments/[id]` com o progress view (mesmo componente usado na saga ao vivo)
- [ ] Mock: 2-3 deployments historicos ja populados (1 success, 1 failed com erro, 1 rodando)

### Sidebar Integration

- [ ] SidebarNav ganha um switcher no topo (Chat / Marketplace / Deployments)
- [ ] Indicador visual do modulo ativo
- [ ] Quando esta em Marketplace/Deployments, a sidebar mostra o contexto apropriado (search de templates, filtros, lista de deploys ativos)
- [ ] No modo Chat, continua como esta hoje

### Componentes (Atomic Design)

- [ ] `atoms/`:
  - `TagPill` — pill pequeno com cor por categoria, reutiliza `AppBadge` mas com size/shape fixos
  - `ProgressBar` — barra horizontal com percentual + transicao CSS

- [ ] `molecules/`:
  - `TemplateCard` — card clicavel com logo, nome, desc, tags, versao, CTA
  - `StepIndicator` — numered steps com estado active/done/pending
  - `LogLine` — linha de log timestamped com icone de nivel (info/warn/error/success)
  - `SagaStep` — linha da saga com icone, nome, status badge, duracao

- [ ] `organisms/`:
  - `MarketplaceGrid` — grid responsivo de TemplateCards com search/filter
  - `TemplateDetail` — pagina de detalhe com metadata + CTA
  - `DeployWizard` — container multi-step com StepIndicator + slots por step
  - `DeployWizardStep1/2/3/4` — sub-organisms por step (formularios)
  - `DeployProgress` — painel de saga + log stream + progress bar
  - `DeploymentsList` — tabela de deployments historicos
  - `ModuleSwitcher` — switcher topo da sidebar (Chat/Marketplace/Deployments)

### Stores e Tipos

- [ ] `types/template.ts` — `Template`, `TemplateCategory`, `EnvVarSchema`, `TemplateChangelog`
- [ ] `types/deployment.ts` — `Deployment`, `DeploymentStatus`, `SagaStep`, `LogEntry`
- [ ] `stores/templates.ts` — Pinia store com 3 templates mockados + `getBySlug`, `search`, `filter`
- [ ] `stores/deployments.ts` — Pinia store com historico mock + `createDeployment(config)` que retorna id + `runSaga(id)` async que atualiza steps reativos + `subscribeLogs(id)` que emite logs simulados via setTimeout

## Dependencies

- **platform-design-namastex_20260410** — tokens CSS (COMPLETE)
- **platform-chat-shell_20260410** — atoms/molecules/organisms reaproveitados + AppShell template (COMPLETE)

## Out of Scope

- Conexao real com Terraform/Databricks SDK (saga e toda mockada com setTimeout)
- Implementacao backend do endpoint de deploy (FastAPI + Celery vira separado)
- Autenticacao de credenciais real (aceita qualquer input)
- Diff visual entre versoes de templates
- Rollback de deployment (botao existe mas e placeholder)
- Upload de templates customizados pelo usuario
- Billing/custos por deployment (proxima track)

## Technical Notes

### Mock da saga de deploy

```ts
// stores/deployments.ts
async function runSaga(deploymentId: string) {
  const steps: SagaStep[] = [
    { id: "validate", name: "Validate credentials", status: "pending" },
    { id: "s3", name: "Create AWS S3 bucket", status: "pending" },
    { id: "secrets", name: "Provision Databricks secrets", status: "pending" },
    { id: "upload", name: "Upload notebooks", status: "pending" },
    { id: "workflow", name: "Create workflow", status: "pending" },
    { id: "trigger", name: "Trigger first run", status: "pending" },
    { id: "register", name: "Register in platform", status: "pending" },
  ]
  deployment.steps = steps

  for (const step of steps) {
    step.status = "running"
    emitLog(deploymentId, { level: "info", message: `Starting ${step.name}...` })
    await new Promise((r) => setTimeout(r, 2000 + Math.random() * 2000))
    step.status = "success"
    emitLog(deploymentId, { level: "success", message: `${step.name} completed` })
  }

  deployment.status = "success"
}
```

### Navegacao pos-deploy

Apos um deploy bem-sucedido, o CTA "Abrir chat deste pipeline" deve:
1. Adicionar o novo pipeline ao `pipelines` store
2. Marcar como `activePipelineId`
3. `navigateTo("/chat")` — o empty state ja reflete o novo pipeline

### Reaproveitamento de componentes

- `AppButton`, `AppInput`, `AppBadge`, `AppIcon`, `AppKbd` — ja existem, reutilizados
- `EmptyState` — reutilizado em `/deployments` quando vazio
- `StatusBadge` — reutilizado nos cards de deployment
- `MessageInput` — reutilizado? (nao, deploy usa formularios padrao)
- `AppShell` — template reaproveitado em todas as pages novas

---

_Generated by Conductor._
