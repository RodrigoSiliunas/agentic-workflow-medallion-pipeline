from types import SimpleNamespace

from observer.workflow_observer import WorkflowObserver


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
    # Sem github_repo/token, reference_code vazio e all_references empty
    assert ctx["reference_code"] == ""
    assert ctx["all_references"] == {}


def test_build_context_passes_git_reference(monkeypatch):
    """build_context puxa git reference quando github_repo/token informados."""
    workspace = SimpleNamespace(jobs=SimpleNamespace())
    observer = WorkflowObserver(workspace)

    monkeypatch.setattr(
        observer,
        "collect_notebook_code",
        lambda run_id: {"bronze_ingestion": "# truncado"},
    )
    monkeypatch.setattr(
        observer,
        "collect_schema_info",
        lambda catalog="medallion", schemas=None: "",
    )
    monkeypatch.setattr(
        observer,
        "collect_git_reference",
        lambda **kwargs: {"bronze_ingestion": "# full from git"},
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
        github_repo="owner/repo",
        github_token="ghp_fake",
    )

    assert ctx["reference_code"] == "# full from git"
    assert ctx["all_references"] == {"bronze_ingestion": "# full from git"}


def test_collect_notebook_code_passes_export_format_enum():
    """collect_notebook_code chama workspace.export com ExportFormat.SOURCE
    enum, nao string. Bug historico: 'SOURCE' string causa
    'str object has no attribute value' no SDK do Databricks.
    """
    import base64

    from databricks.sdk.service.workspace import ExportFormat

    captured_format = {}

    def fake_export(path: str, format):  # noqa: A002
        captured_format["value"] = format
        return SimpleNamespace(
            content=base64.b64encode(b"print('ok')").decode("ascii"),
        )

    run = SimpleNamespace(
        run_id=42,
        tasks=[
            SimpleNamespace(
                task_key="bronze",
                run_id=1,
                notebook_task=SimpleNamespace(notebook_path="/Shared/x/repo/nb"),
            )
        ],
    )
    workspace = SimpleNamespace(
        jobs=SimpleNamespace(get_run=lambda run_id: run),
        workspace=SimpleNamespace(export=fake_export),
    )

    observer = WorkflowObserver(workspace)
    codes = observer.collect_notebook_code(run_id=42)

    assert captured_format["value"] is ExportFormat.SOURCE
    assert codes["bronze"] == "print('ok')"


def test_restore_workspace_file_chama_import_com_format_source():  # noqa: N802
    """restore_workspace_file usa workspace.import_ com formato SOURCE +
    language enum, overwrite=True. base64 do content e calculado.
    """
    import base64

    from databricks.sdk.service.workspace import ImportFormat, Language

    captured: dict = {}

    def fake_import_(**kwargs):
        captured.update(kwargs)

    workspace = SimpleNamespace(
        workspace=SimpleNamespace(import_=fake_import_),
        jobs=SimpleNamespace(),
    )
    observer = WorkflowObserver(workspace)
    observer.restore_workspace_file(
        "/Shared/x/repo/notebooks/bronze/ingest",
        "print('hello')",
        language="PYTHON",
    )

    assert captured["path"] == "/Shared/x/repo/notebooks/bronze/ingest"
    assert captured["format"] is ImportFormat.SOURCE
    assert captured["language"] is Language.PYTHON
    assert captured["overwrite"] is True
    assert base64.b64decode(captured["content"]).decode() == "print('hello')"


def test_collect_notebook_workspace_paths_mapeia_task_para_path():
    run = SimpleNamespace(
        run_id=1,
        tasks=[
            SimpleNamespace(
                task_key="bronze",
                notebook_task=SimpleNamespace(notebook_path="/Shared/x/bronze"),
            ),
            SimpleNamespace(
                task_key="silver",
                notebook_task=SimpleNamespace(notebook_path="/Shared/x/silver"),
            ),
            SimpleNamespace(
                task_key="spark_task",
                notebook_task=None,  # Spark/python task — sem notebook
            ),
        ],
    )
    workspace = SimpleNamespace(jobs=SimpleNamespace(get_run=lambda run_id: run))
    observer = WorkflowObserver(workspace)
    paths = observer.collect_notebook_workspace_paths(run_id=1)
    assert paths == {
        "bronze": "/Shared/x/bronze",
        "silver": "/Shared/x/silver",
    }


def test_repo_path_re_matches_shared_and_repos():
    """_REPO_PATH_RE extrai path repo-relative de workspace paths."""
    from observer.workflow_observer import _REPO_PATH_RE

    m1 = _REPO_PATH_RE.match(
        "/Shared/flowertex/agentic-workflow-medallion-pipeline/"
        "pipelines/seguradora/notebooks/bronze/ingest"
    )
    assert m1 is not None
    assert m1.group("repo") == "agentic-workflow-medallion-pipeline"
    assert m1.group("path") == "pipelines/seguradora/notebooks/bronze/ingest"

    m2 = _REPO_PATH_RE.match(
        "/Repos/user@example.com/agentic-workflow-medallion-pipeline/"
        "pipelines/seguradora/notebooks/silver/dedup_clean"
    )
    assert m2 is not None
    assert m2.group("repo") == "agentic-workflow-medallion-pipeline"
    assert m2.group("path") == "pipelines/seguradora/notebooks/silver/dedup_clean"

    assert _REPO_PATH_RE.match("/Workspace/Users/x/notebooks/foo") is None
