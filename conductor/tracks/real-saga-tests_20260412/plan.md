# Plan: Real Saga Tests

## Phase 1: Test infrastructure
- [ ] Task 1: Criar tests/factories.py com make_deployment, make_credentials, make_step_context
- [ ] Task 2: Adicionar fixtures compartilhados no conftest.py

## Phase 2: Backend unit tests
- [ ] Task 3: test_terraform_runner.py (mock subprocess, test init/apply/output/error)
- [ ] Task 4: test_step_validate.py (mock boto3 STS + httpx)
- [ ] Task 5: test_step_s3.py (mock head_bucket + terraform fallback)
- [ ] Task 6: test_credential_service.py (encrypt/decrypt, type validation, test_credential)
- [ ] Task 7: test_runner.py (dispatch, unknown step, missing credentials, shared state cleanup)

## Phase 3: Integration tests
- [ ] Task 8: test_deployments.py — saga end-to-end com MockRunner, verify DB state final

## Phase 4: Frontend tests
- [ ] Task 9: auth.test.ts (JWT decode, expiration, initFromStorage, mock mode)
- [ ] Task 10: deployments.test.ts (createDeployment, runSagaMock, getById)
