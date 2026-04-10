from types import SimpleNamespace

from pipeline_lib.agent.observer.workflow_observer import WorkflowObserver


def make_task(task_key: str, result_state: str, run_id: int):
    return SimpleNamespace(
        task_key=task_key,
        run_id=run_id,
        state=SimpleNamespace(result_state=result_state),
        notebook_task=SimpleNamespace(notebook_path=f"/Repos/demo/{task_key}"),
    )


def test_build_failure_from_run_prefers_root_failed_tasks():
    run = SimpleNamespace(
        run_id=123,
        job_id=777,
        run_name="medallion_pipeline_whatsapp",
        start_time=1710000000,
        tasks=[
            make_task("bronze_ingestion", "FAILED", 1001),
            make_task("quality_validation", "UPSTREAM_FAILED", 1002),
        ],
    )

    workspace = SimpleNamespace(
        jobs=SimpleNamespace(
            get_run=lambda run_id: run,
            get_run_output=lambda run_id: SimpleNamespace(error=f"boom-{run_id}"),
        )
    )

    observer = WorkflowObserver(workspace)
    failure = observer.build_failure_from_run(run_id=123)

    assert failure["job_id"] == 777
    assert failure["failed_tasks"] == ["bronze_ingestion"]
    assert failure["errors"] == {"bronze_ingestion": "boom-1001"}


def test_build_context_uses_catalog_override(monkeypatch):
    workspace = SimpleNamespace(jobs=SimpleNamespace())
    observer = WorkflowObserver(workspace)

    monkeypatch.setattr(
        observer,
        "collect_notebook_code",
        lambda run_id: {"bronze_ingestion": "print('ok')"},
    )
    monkeypatch.setattr(
        observer,
        "collect_schema_info",
        lambda catalog="medallion", schemas=None: f"catalog={catalog}",
    )

    ctx = observer.build_context(
        {
            "job_name": "medallion_pipeline_whatsapp",
            "job_id": 777,
            "run_id": 123,
            "failed_tasks": ["bronze_ingestion"],
            "errors": {"bronze_ingestion": "boom"},
            "timestamp": "1710000000",
        },
        catalog="custom",
    )

    assert ctx["schema_info"] == "catalog=custom"
    assert ctx["failed_task"] == "bronze_ingestion"
