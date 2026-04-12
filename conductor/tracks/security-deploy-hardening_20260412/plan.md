# Plan: Security Deploy Hardening

## Phase 1: Terraform output sanitization
- [ ] Task 1: Create `_sanitize_log(line)` helper in terraform_runner.py — regex-replace known secret patterns
- [ ] Task 2: Apply sanitizer before emit_log and before TerraformError stderr capture

## Phase 2: Subprocess environment isolation
- [ ] Task 3: In terraform_runner.py, build minimal env dict (PATH, HOME, TMP only) instead of {**os.environ, **self.env}

## Phase 3: Client caching fix
- [ ] Task 4: Remove lru_cache from databricks_client.py, instantiate per-call (SDK pools connections internally)

## Phase 4: Exception message sanitization
- [ ] Task 5: In deployment_saga.py error handler, replace str(exc) with generic message for SSE, keep full trace in server logs
