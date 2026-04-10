from types import SimpleNamespace

from observer.triggering import (
    build_observer_notebook_params,
    extract_failed_task_keys,
    parse_failed_tasks_param,
    resolve_runtime_context,
)


def make_task(task_key: str, result_state: str):
    return SimpleNamespace(
        task_key=task_key,
        state=SimpleNamespace(result_state=result_state),
    )


def test_extract_failed_task_keys_prefers_root_failures():
    tasks = [
        make_task("bronze_ingestion", "SUCCESS"),
        make_task("silver_entities", "FAILED"),
        make_task("quality_validation", "UPSTREAM_FAILED"),
    ]

    assert extract_failed_task_keys(tasks) == ["silver_entities"]


def test_extract_failed_task_keys_falls_back_to_upstream_failed():
    tasks = [
        make_task("gold_analytics", "UPSTREAM_FAILED"),
        make_task("quality_validation", "UPSTREAM_FAILED"),
    ]

    assert extract_failed_task_keys(tasks) == ["gold_analytics", "quality_validation"]


def test_parse_failed_tasks_param_accepts_json_and_csv():
    assert parse_failed_tasks_param('["bronze_ingestion", "gold_analytics"]') == [
        "bronze_ingestion",
        "gold_analytics",
    ]
    assert parse_failed_tasks_param("bronze_ingestion, gold_analytics") == [
        "bronze_ingestion",
        "gold_analytics",
    ]


def test_build_observer_notebook_params_serializes_metadata():
    params = build_observer_notebook_params(
        catalog="medallion",
        scope="medallion-pipeline",
        source_run_id=123,
        source_job_id=456,
        source_job_name="medallion_pipeline_whatsapp",
        failed_tasks=["bronze_ingestion", "gold_analytics"],
    )

    assert params["catalog"] == "medallion"
    assert params["scope"] == "medallion-pipeline"
    assert params["source_run_id"] == "123"
    assert params["source_job_id"] == "456"
    assert params["source_job_name"] == "medallion_pipeline_whatsapp"
    assert params["failed_tasks"] == '["bronze_ingestion", "gold_analytics"]'


def test_resolve_runtime_context_prefers_parent_run_id():
    runtime = resolve_runtime_context(
        {
            "jobId": "777105089901314",
            "multitaskParentRunId": "987654321",
            "runId": "12345",
            "taskKey": "observer_trigger",
        },
        current_run_id=111,
    )

    assert runtime.parent_run_id == 987654321
    assert runtime.job_id == 777105089901314
    assert runtime.task_key == "observer_trigger"
