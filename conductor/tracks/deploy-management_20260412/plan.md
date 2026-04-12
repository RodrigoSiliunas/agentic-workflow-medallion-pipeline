# Plan: Deploy Management

## Phase 1: Backend
- [ ] Task 1: Adicionar DELETE /deployments/{id} endpoint — hard delete com CASCADE (steps + logs)
- [ ] Task 2: Se deployment.status == "running", chamar request_cancel antes de deletar

## Phase 2: Frontend
- [ ] Task 3: Botao "Excluir" no deployment detail page (com confirmacao)
- [ ] Task 4: Botao de excluir na lista de deployments (icon trash)
- [ ] Task 5: Store action deleteDeployment + API call
