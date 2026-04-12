# Deploy Management — Delete Deployment

## Problema
O usuario nao consegue excluir deployments do UI. Nao ha endpoint DELETE nem botao na interface.
Deployments de teste acumulam na lista sem opcao de cleanup.

## Solucao
1. Backend: DELETE /api/v1/deployments/{id} — soft delete ou hard delete com CASCADE
2. Frontend: botao de excluir no deployment detail page e na lista
3. Confirmacao modal antes de deletar
4. Cancelar saga em andamento antes de deletar (se status=running)
