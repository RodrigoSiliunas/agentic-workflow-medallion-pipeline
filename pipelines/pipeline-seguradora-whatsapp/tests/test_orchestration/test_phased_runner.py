"""Testes do PhasedNotebookRunner (T6 Phase 2)."""

from __future__ import annotations

import threading

from pipeline_lib.orchestration import PhasedNotebookRunner


class _FakeDbutils:
    """Stub — runner é injetado nos testes, então dbutils fica vazio."""


class TestFromDict:
    def test_parses_phases_in_order(self):
        config = {
            "phases": [
                {"name": "A", "notebooks": [{"name": "x", "path": "/p/x"}]},
                {
                    "name": "B",
                    "notebooks": [
                        {"name": "y", "path": "/p/y"},
                        {"name": "z", "path": "/p/z"},
                    ],
                },
            ]
        }
        runner = PhasedNotebookRunner.from_dict(config)
        assert runner._phases[0][0] == "A"
        assert runner._phases[1][0] == "B"
        assert runner._phases[1][1] == [("y", "/p/y"), ("z", "/p/z")]

    def test_empty_config(self):
        runner = PhasedNotebookRunner.from_dict({})
        assert runner._phases == []


class TestFromYaml:
    def test_loads_yaml_file(self, tmp_path):
        yml = tmp_path / "phases.yaml"
        yml.write_text(
            "phases:\n"
            "  - name: core\n"
            "    notebooks:\n"
            "      - name: funnel\n"
            "        path: gold/funnel\n",
            encoding="utf-8",
        )
        runner = PhasedNotebookRunner.from_yaml(yml)
        assert runner._phases == [("core", [("funnel", "gold/funnel")])]


class TestRunSequencing:
    def test_phases_run_in_declared_order(self):
        runner = PhasedNotebookRunner([
            ("A", [("a1", "/p/a1")]),
            ("B", [("b1", "/p/b1")]),
            ("C", [("c1", "/p/c1")]),
        ])

        order: list[str] = []

        def fake_run(path: str, _to: int) -> str:
            order.append(path)
            return "ok"

        results = runner.run(_FakeDbutils(), runner=fake_run)
        # Ordem por fase preservada
        assert order == ["/p/a1", "/p/b1", "/p/c1"]
        assert [r.phase_name for r in results] == ["A", "B", "C"]

    def test_parallel_within_phase(self):
        """Notebooks da mesma fase rodam concorrente — checamos overlap."""
        active = []
        max_seen = 0
        lock = threading.Lock()

        def slow_run(path: str, _to: int) -> str:
            nonlocal max_seen
            with lock:
                active.append(path)
                max_seen = max(max_seen, len(active))
            # Pequeno sleep pra garantir que outras threads entrem
            import time

            time.sleep(0.05)
            with lock:
                active.remove(path)
            return "ok"

        runner = PhasedNotebookRunner([
            ("parallel", [("n1", "/a"), ("n2", "/b"), ("n3", "/c")]),
        ])
        runner.run(_FakeDbutils(), runner=slow_run)
        # Pelo menos 2 notebooks overlap (parallelismo)
        assert max_seen >= 2


class TestFailureHandling:
    def test_single_notebook_failure_does_not_stop_phase(self):
        def fake(path: str, _to: int) -> str:
            if path == "/bad":
                raise RuntimeError("boom")
            return "ok"

        runner = PhasedNotebookRunner([
            ("phase1", [("good", "/good"), ("bad", "/bad"), ("also", "/also")]),
        ])
        results = runner.run(_FakeDbutils(), runner=fake)
        phase = results[0]
        assert not phase.succeeded
        assert len(phase.errors) == 1
        assert "bad:" in phase.errors[0]
        # Os demais ainda executaram
        assert phase.results["good"] == "ok"
        assert phase.results["also"] == "ok"
        assert phase.results["bad"].startswith("FAILED")

    def test_abort_on_phase_failure_skips_remaining(self):
        def fake(path: str, _to: int) -> str:
            if path == "/fail":
                raise RuntimeError("x")
            return "ok"

        runner = PhasedNotebookRunner([
            ("phase1", [("n1", "/fail")]),
            ("phase2", [("n2", "/ok")]),
        ])
        results = runner.run(_FakeDbutils(), runner=fake, abort_on_phase_failure=True)
        assert len(results) == 1
        assert results[0].phase_name == "phase1"

    def test_continue_on_phase_failure_by_default(self):
        def fake(path: str, _to: int) -> str:
            if path == "/fail":
                raise RuntimeError("x")
            return "ok"

        runner = PhasedNotebookRunner([
            ("phase1", [("n1", "/fail")]),
            ("phase2", [("n2", "/ok")]),
        ])
        results = runner.run(_FakeDbutils(), runner=fake)
        assert len(results) == 2
        assert results[1].results["n2"] == "ok"


class TestEmptyPhases:
    def test_empty_phase_returns_empty_result(self):
        runner = PhasedNotebookRunner([("empty", [])])
        results = runner.run(_FakeDbutils(), runner=lambda *_: "ok")
        assert results[0].results == {}
        assert results[0].succeeded


class TestSafeRun:
    def test_catches_exception_as_failed_string(self):
        def boom(_p, _t):
            raise ValueError("kaboom")

        runner = PhasedNotebookRunner([("p", [("n", "/x")])])
        results = runner.run(_FakeDbutils(), runner=boom)
        assert results[0].results["n"].startswith("FAILED")
        assert "kaboom" in results[0].results["n"]
