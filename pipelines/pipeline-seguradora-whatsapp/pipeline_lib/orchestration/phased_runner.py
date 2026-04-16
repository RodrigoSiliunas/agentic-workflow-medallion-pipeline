"""PhasedNotebookRunner (T6 Phase 2).

Extraído de `notebooks/gold/analytics.py:43-106`. Executa fases
sequenciais, notebooks dentro de cada fase em paralelo via ThreadPool.

Fase 2 só começa depois de fase 1 terminar (todos os notebooks dela).
Dentro de cada fase, `max_workers = len(notebooks)` — cada notebook roda
em sua própria thread.

Config YAML (opcional):

    phases:
      - name: Core
        notebooks:
          - name: funnel
            path: notebooks/gold/funnel
          - name: sentiment
            path: notebooks/gold/sentiment
      - name: Scoring
        notebooks:
          - name: lead_scoring
            path: notebooks/gold/lead_scoring

Uso:
    from pipeline_lib.orchestration import PhasedNotebookRunner

    runner = PhasedNotebookRunner.from_yaml(path)
    results = runner.run(dbutils, timeout=1200)
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class PhaseResult:
    """Resultado da execução de uma fase."""

    phase_name: str
    results: dict[str, str] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)

    @property
    def succeeded(self) -> bool:
        return not self.errors


NotebookSpec = tuple[str, str]  # (name, path)
_Runner = Callable[[str, int], str]


class PhasedNotebookRunner:
    """Orquestra fases sequenciais de notebooks paralelos.

    Cada fase é uma lista de `(name, path)`. Fases rodam em ordem.
    Notebooks dentro da fase rodam concorrentemente; se algum falhar,
    registramos e continuamos — o caller decide se aborta fases
    subsequentes.
    """

    def __init__(self, phases: list[tuple[str, list[NotebookSpec]]]) -> None:
        self._phases = phases

    @classmethod
    def from_dict(cls, config: dict) -> PhasedNotebookRunner:
        """Constroi a partir de dict YAML-compatível."""
        phases: list[tuple[str, list[NotebookSpec]]] = []
        for phase in config.get("phases", []):
            name = phase["name"]
            nbs = [
                (nb["name"], nb["path"])
                for nb in phase.get("notebooks", [])
            ]
            phases.append((name, nbs))
        return cls(phases)

    @classmethod
    def from_yaml(cls, path: str | Path) -> PhasedNotebookRunner:
        """Carrega config de um arquivo YAML e constroi o runner."""
        import yaml  # noqa: PLC0415

        with Path(path).open(encoding="utf-8") as handle:
            config = yaml.safe_load(handle)
        return cls.from_dict(config or {})

    def run(
        self,
        dbutils,
        timeout: int = 1800,
        abort_on_phase_failure: bool = False,
        runner: _Runner | None = None,
    ) -> list[PhaseResult]:
        """Executa todas as fases. Retorna lista de PhaseResult.

        Args:
            dbutils: Databricks dbutils — usamos `dbutils.notebook.run`
                por padrão. Em testes, injete `runner` pra evitar.
            timeout: segundos por notebook.
            abort_on_phase_failure: se True, para de executar fases
                depois da primeira fase com erro.
            runner: Callable `(path, timeout) -> result_str` usado em
                testes. Default chama `dbutils.notebook.run`.
        """
        run_one = runner or (
            lambda path, to: dbutils.notebook.run(path, to)  # noqa: E731
        )

        all_results: list[PhaseResult] = []
        for phase_name, nbs in self._phases:
            phase_result = self._run_phase(phase_name, nbs, timeout, run_one)
            all_results.append(phase_result)
            if abort_on_phase_failure and not phase_result.succeeded:
                logger.warning(
                    "abort after phase %s — pulando fases restantes",
                    phase_name,
                )
                break
        return all_results

    def _run_phase(
        self,
        phase_name: str,
        nbs: list[NotebookSpec],
        timeout: int,
        run_one: _Runner,
    ) -> PhaseResult:
        logger.info(
            "phase start: %s (%d notebooks em paralelo)",
            phase_name,
            len(nbs),
        )
        result = PhaseResult(phase_name=phase_name)
        if not nbs:
            return result

        with ThreadPoolExecutor(max_workers=len(nbs)) as executor:
            futures = {
                executor.submit(self._safe_run, run_one, name, path, timeout): name
                for name, path in nbs
            }
            for future in as_completed(futures):
                name, output = future.result()
                result.results[name] = output
                if str(output).startswith("FAILED"):
                    result.errors.append(f"{name}: {output}")
                    logger.error("  FALHOU: %s", name)
                else:
                    logger.info("  OK: %s", name)
        return result

    @staticmethod
    def _safe_run(
        run_one: _Runner, name: str, path: str, timeout: int
    ) -> tuple[str, str]:
        try:
            return (name, str(run_one(path, timeout)))
        except Exception as exc:  # noqa: BLE001
            return (name, f"FAILED: {exc}")
