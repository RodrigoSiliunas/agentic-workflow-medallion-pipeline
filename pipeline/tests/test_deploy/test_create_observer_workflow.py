from types import SimpleNamespace

from deploy import create_observer_workflow as create_observer_workflow_module


class FakeJobsAPI:
    def __init__(self, observer_job_ids=None):
        self.observer_job_ids = observer_job_ids or []
        self.created_payload = None
        self.reset_calls = []

    def list(self, name=None):
        if name == create_observer_workflow_module.WORKFLOW_NAME:
            return [
                SimpleNamespace(job_id=job_id, settings=SimpleNamespace(name=name))
                for job_id in self.observer_job_ids
            ]
        return []

    def create(self, **kwargs):
        self.created_payload = kwargs
        return SimpleNamespace(job_id=848172838529828)

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


def test_create_observer_workflow_includes_trigger_metadata(monkeypatch):
    jobs_api = FakeJobsAPI()

    monkeypatch.setattr(
        create_observer_workflow_module,
        "WorkspaceClient",
        make_workspace_client(jobs_api),
    )
    monkeypatch.setattr(create_observer_workflow_module, "CLUSTER_ID", "cluster-123")
    monkeypatch.setenv("DATABRICKS_HOST", "https://example.databricks.com")
    monkeypatch.setenv("DATABRICKS_TOKEN", "token")

    job_id = create_observer_workflow_module.create_observer()

    assert job_id == 848172838529828
    assert jobs_api.reset_calls == []
    task = jobs_api.created_payload["tasks"][0]
    assert task["notebook_task"]["base_parameters"]["catalog"] == "medallion"
    assert task["notebook_task"]["base_parameters"]["source_job_name"] == ""
    assert task["notebook_task"]["base_parameters"]["failed_tasks"] == "[]"
    assert task["notebook_task"]["base_parameters"]["llm_provider"] == "anthropic"
    assert task["notebook_task"]["base_parameters"]["git_provider"] == "github"


def test_create_observer_workflow_updates_latest_job(monkeypatch):
    jobs_api = FakeJobsAPI(observer_job_ids=[111, 222])

    monkeypatch.setattr(
        create_observer_workflow_module,
        "WorkspaceClient",
        make_workspace_client(jobs_api),
    )
    monkeypatch.setattr(create_observer_workflow_module, "CLUSTER_ID", "cluster-123")
    monkeypatch.setenv("DATABRICKS_HOST", "https://example.databricks.com")
    monkeypatch.setenv("DATABRICKS_TOKEN", "token")

    job_id = create_observer_workflow_module.create_observer()

    assert job_id == 222
    assert jobs_api.created_payload is None
    assert len(jobs_api.reset_calls) == 1
    reset_job_id, job_settings = jobs_api.reset_calls[0]
    assert reset_job_id == 222
    task = job_settings.tasks[0]
    assert task.notebook_task.base_parameters["failed_tasks"] == "[]"
