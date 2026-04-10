# Track: Observer - Feedback Loop

**ID:** observer-feedback_20260409
**Status:** Complete

## Documents

- [Specification](./spec.md)
- [Implementation Plan](./plan.md)

## Progress

- Phases: 3/3 complete
- Tasks: 9/9 complete

## Validation Runs

- **Migracao de schema**: 4 colunas (`pr_status`, `pr_resolved_at`, `resolution_time_hours`, `feedback`) adicionadas em `medallion.observer.diagnostics` via `ALTER TABLE ADD COLUMNS` (idempotente por `_migrate_columns`)
- **Script CLI**:
  - `update_pr_feedback.py --pr-number 7 --status merged` -> `status=merged, feedback=fix_accepted (1 record atualizado)`
  - `update_pr_feedback.py --pr-number 8 --status closed` -> `status=closed, feedback=fix_rejected (1 record atualizado)`
- **Dashboard queries**:
  - Painel 9 (taxa de aceitacao): 1 pending, 1 merged, 1 closed
  - Painel 11 (eficacia por provider): anthropic/claude-opus-4 -> 3 criados, 1 aceito, 1 rejeitado
- **GitHub Action**: `.github/workflows/observer-feedback.yml` pronta para disparar automaticamente quando PRs `fix/agent-auto-*` forem fechados/mergeados na proxima vez

## Quick Links

- [Back to Tracks](../../tracks.md)
- [Product Context](../../product.md)
