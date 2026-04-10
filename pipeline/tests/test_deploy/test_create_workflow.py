from types import SimpleNamespace

from databricks.sdk.service.jobs import RunIf

from deploy import create_workflow as create_workflow_module


class FakeJobsAPI:
    def __init__(self, pipeline_job_ids=None, observer_job_ids=None):
        self.pipeline_job_ids = pipeline_job_ids or []
        self.observer_job_ids = observer_job_ids or []
        self.created_payload = None
        self.reset_calls = []

    def list(self, name=None):
        if name == create_workflow_module.WORKFLOW_NAME:
            return [
                SimpleNamespace(job_id=job_id, settings=SimpleNamespace(name=name))
                for job_id in self.pipeline_job_ids
            ]
        if name == create_workflow_module.OBSERVER_JOB_NAME:
            return [
                SimpleNamespace(job_id=job_id, settings=SimpleNamespace(name=name))
                for job_id in self.observer_job_ids
            ]
        return []

    def create(self, **kwargs):
        self.created_payload = kwargs
        return SimpleNamespace(job_id=777105089901314)

    def reset(self, job_id, new_settings):
        self.reset_calls.append((job_id, new_settings))


def make_workspace_client(jobs_api):
    class FakeWorkspaceClient:
        def __init__(self, *args, **kwargs):
            self.current_user = SimpleNamespace(
                me=lambda: SimpleNamespace(user_name="administrator@idlehub.com.br")
            )
            self.jobs = jobs_api

    return FakeWorkspaceClient


def test_create_workflow_creates_job_when_missing(monkeypatch):
    jobs_api = FakeJobsAPI(observer_job_ids=[848172838529828])

    monkeypatch.setattr(
        create_workflow_module,
        "WorkspaceClient",
        make_workspace_client(jobs_api),
    )
    monkeypatch.setattr(create_workflow_module, "CLUSTER_ID", "cluster-123")
    monkeypatch.setattr(create_workflow_module, "OBSERVER_JOB_ID", "")
    monkeypatch.setattr(
        create_workflow_module,
        "OBSERVER_JOB_NAME",
        "workflow_observer_agent",
    )
    monkeypatch.setenv("DATABRICKS_HOST", "https://example.databricks.com")
    monkeypatch.setenv("DATABRICKS_TOKEN", "token")

    job_id = create_workflow_module.create_workflow()

    assert job_id == 777105089901314
    assert jobs_api.reset_calls == []
    tasks = {task["task_key"]: task for task in jobs_api.created_payload["tasks"]}
    assert "agent_pre" in tasks
    assert "agent_post" in tasks
    assert "observer_trigger" in tasks
    assert tasks["agent_post"]["run_if"] == RunIf.ALL_DONE.value
    assert tasks["observer_trigger"]["run_if"] == RunIf.AT_LEAST_ONE_FAILED.value
    assert tasks["observer_trigger"]["notebook_task"]["base_parameters"]["observer_job_id"] == (
        "848172838529828"
    )


def test_create_workflow_updates_latest_existing_job(monkeypatch):
    jobs_api = FakeJobsAPI(
        pipeline_job_ids=[111, 222],
        observer_job_ids=[848172838529828],
    )

    monkeypatch.setattr(
        create_workflow_module,
        "WorkspaceClient",
        make_workspace_client(jobs_api),
    )
    monkeypatch.setattr(create_workflow_module, "CLUSTER_ID", "cluster-123")
    monkeypatch.setattr(create_workflow_module, "OBSERVER_JOB_ID", "")
    monkeypatch.setenv("DATABRICKS_HOST", "https://example.databricks.com")
    monkeypatch.setenv("DATABRICKS_TOKEN", "token")

    job_id = create_workflow_module.create_workflow()

    assert job_id == 222
    assert jobs_api.created_payload is None
    assert len(jobs_api.reset_calls) == 1
    reset_job_id, job_settings = jobs_api.reset_calls[0]
    assert reset_job_id == 222
    tasks = {task.task_key: task for task in job_settings.tasks}
    assert [dep.task_key for dep in tasks["bronze_ingestion"].depends_on] == ["agent_pre"]
    assert [dep.task_key for dep in tasks["agent_post"].depends_on] == ["quality_validation"]
    assert "agent_post" in [dep.task_key for dep in tasks["observer_trigger"].depends_on]
