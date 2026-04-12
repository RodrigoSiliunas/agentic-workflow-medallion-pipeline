# Plan: Security Critical Config

## Phase 1: Config validation + SQL injection fix
- [ ] Task 1: Add startup validation in security.py — raise RuntimeError if ENCRYPTION_KEY is default
- [ ] Task 2: Add startup validation in config.py or main.py — raise RuntimeError if SECRET_KEY is default when SAGA_RUNNER=real
- [ ] Task 3: Add catalog name regex validation in catalog.py step
- [ ] Task 4: Generate real Fernet key and JWT secret, update .env
- [ ] Task 5: Run tests to verify nothing breaks
