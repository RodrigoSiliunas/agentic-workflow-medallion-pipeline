# Plan: Deploy Performance

## Phase 1: DB commits
- [ ] Task 1: emit_log usa flush (sem commit), commit apenas em boundaries de step

## Phase 2: Parallel operations
- [ ] Task 2: Credential resolution com get_all_decrypted() — 1 query instead of 8
- [ ] Task 3: Validate step usa asyncio.gather pros 4 checks
- [ ] Task 4: Secrets step usa asyncio.gather pra put_secret
- [ ] Task 5: Catalog step usa asyncio.gather pra CREATE SCHEMA

## Phase 3: SSE reliability
- [ ] Task 6: SSE queue com drop-oldest + terminal event guarantee
