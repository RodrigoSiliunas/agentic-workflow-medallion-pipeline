"""Unit tests para TerraformRunner com subprocess mockado."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.real_saga.terraform_runner import (
    TerraformError,
    TerraformRunner,
    _sanitize_log_line,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_runner(
    *,
    module_source: Path | None = None,
    workspace: Path | None = None,
    env: dict | None = None,
    emit_log: AsyncMock | None = None,
) -> TerraformRunner:
    return TerraformRunner(
        module_source=module_source or Path("/fake/infra/02-datalake"),
        workspace=workspace or Path("/fake/workdir"),
        env=env or {},
        emit_log=emit_log or AsyncMock(),
    )


def _make_fake_process(
    *,
    stdout_lines: list[str] | None = None,
    stderr_lines: list[str] | None = None,
    returncode: int = 0,
):
    """Cria um mock de asyncio.Process com stdout/stderr streamaveis."""
    proc = MagicMock()
    proc.wait = AsyncMock(return_value=returncode)

    # Monta stream de stdout
    stdout_data = "\n".join(stdout_lines or [])
    if stdout_data:
        stdout_data += "\n"
    stdout_reader = MagicMock()
    _stdout_lines = (stdout_data.encode()).split(b"\n") if stdout_data else []
    # readline retorna linha por linha, depois b""
    _stdout_iter = iter([line + b"\n" for line in _stdout_lines if line] + [b""])
    stdout_reader.readline = AsyncMock(side_effect=lambda: next(_stdout_iter))
    proc.stdout = stdout_reader

    # Monta stream de stderr
    stderr_data = "\n".join(stderr_lines or [])
    if stderr_data:
        stderr_data += "\n"
    stderr_reader = MagicMock()
    _stderr_lines = (stderr_data.encode()).split(b"\n") if stderr_data else []
    _stderr_iter = iter([line + b"\n" for line in _stderr_lines if line] + [b""])
    stderr_reader.readline = AsyncMock(side_effect=lambda: next(_stderr_iter))
    proc.stderr = stderr_reader

    return proc


# ---------------------------------------------------------------------------
# Tests: ensure_workspace
# ---------------------------------------------------------------------------


class TestEnsureWorkspace:
    async def test_ensure_workspace_copies_tf_files(self, tmp_path: Path):
        """Verifica que .tf files sao copiados do source pro workspace."""
        source = tmp_path / "source"
        source.mkdir()
        (source / "main.tf").write_text("resource {}")
        (source / "variables.tf").write_text("variable {}")
        (source / "README.md").write_text("# nao copiar")

        workspace = tmp_path / "workspace"
        emit = AsyncMock()
        runner = _make_runner(module_source=source, workspace=workspace, emit_log=emit)

        await runner.ensure_workspace()

        assert (workspace / "main.tf").exists()
        assert (workspace / "variables.tf").exists()
        assert not (workspace / "README.md").exists()
        emit.assert_awaited_once()

    async def test_ensure_workspace_noop_if_tf_files_exist(self, tmp_path: Path):
        """Se o workspace ja tem .tf files, nao copia novamente."""
        source = tmp_path / "source"
        source.mkdir()
        (source / "main.tf").write_text("resource {}")

        workspace = tmp_path / "workspace"
        workspace.mkdir()
        (workspace / "existing.tf").write_text("already here")

        emit = AsyncMock()
        runner = _make_runner(module_source=source, workspace=workspace, emit_log=emit)

        await runner.ensure_workspace()

        # Nao deve copiar — workspace ja tem .tf
        assert (workspace / "existing.tf").read_text() == "already here"
        assert not (workspace / "main.tf").exists()
        emit.assert_not_awaited()


# ---------------------------------------------------------------------------
# Tests: _sanitize_log_line
# ---------------------------------------------------------------------------


class TestSanitizeLogLine:
    def test_sanitize_log_line_redacts_aws_key(self):
        line = "Using access key AKIAIOSFODNN7EXAMPLE for auth"
        result = _sanitize_log_line(line)
        assert "AKIAIOSFODNN7EXAMPLE" not in result
        assert "AKIA" in result
        assert "REDACTED" in result

    def test_sanitize_log_line_redacts_databricks_token(self):
        line = "token=dapi1234abcdef567890abcdef1234"
        result = _sanitize_log_line(line)
        assert "dapi1234abcdef567890abcdef1234" not in result
        assert "REDACTED" in result

    def test_sanitize_log_line_redacts_github_pat(self):
        line = "auth: ghp_abc123def456ghi789jkl012mno345"
        result = _sanitize_log_line(line)
        assert "ghp_abc123def456ghi789jkl012mno345" not in result
        assert "REDACTED" in result

    def test_sanitize_log_line_passes_normal_text(self):
        line = "Terraform v1.9.0 on linux_amd64 — Plan: 3 to add, 0 to change"
        result = _sanitize_log_line(line)
        assert result == line


# ---------------------------------------------------------------------------
# Tests: _run (via init/apply) com subprocess mockado
# ---------------------------------------------------------------------------


class TestTerraformRun:
    @patch("app.services.real_saga.terraform_runner.asyncio.create_subprocess_exec")
    async def test_run_raises_terraform_error_on_nonzero_exit(
        self, mock_exec: MagicMock, tmp_path: Path
    ):
        """Subprocess retornando exit code 1 deve levantar TerraformError."""
        source = tmp_path / "source"
        source.mkdir()
        (source / "main.tf").write_text("resource {}")

        workspace = tmp_path / "workspace"
        workspace.mkdir()
        (workspace / "main.tf").write_text("resource {}")

        fake_proc = _make_fake_process(
            stderr_lines=["Error: bucket already exists"],
            returncode=1,
        )
        mock_exec.return_value = fake_proc

        emit = AsyncMock()
        runner = _make_runner(module_source=source, workspace=workspace, emit_log=emit)

        with pytest.raises(TerraformError) as exc_info:
            await runner.apply()

        assert exc_info.value.returncode == 1
        assert "bucket already exists" in exc_info.value.stderr

    @patch("app.services.real_saga.terraform_runner.asyncio.create_subprocess_exec")
    async def test_run_success_does_not_raise(
        self, mock_exec: MagicMock, tmp_path: Path
    ):
        """Subprocess retornando exit code 0 nao levanta exception."""
        source = tmp_path / "source"
        source.mkdir()
        (source / "main.tf").write_text("resource {}")

        workspace = tmp_path / "workspace"
        workspace.mkdir()
        (workspace / "main.tf").write_text("resource {}")

        fake_proc = _make_fake_process(
            stdout_lines=["Apply complete! Resources: 1 added, 0 changed, 0 destroyed."],
            returncode=0,
        )
        mock_exec.return_value = fake_proc

        emit = AsyncMock()
        runner = _make_runner(module_source=source, workspace=workspace, emit_log=emit)

        # Nao deve levantar exception
        await runner.apply()

        # emit_log deve ter sido chamado com linhas do stdout
        assert emit.await_count >= 1
