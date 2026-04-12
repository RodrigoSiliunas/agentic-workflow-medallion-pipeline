"""Wrapper do CLI `terraform` com streaming de logs reativos.

Cada company tem um workspace proprio em `data/terraform/{company_id}/{module}/`.
Os .tf files sao copiados de `infra/aws/{module}/` no primeiro run e o state
fica local ao workspace — isso permite que multiplos tenants tenham state files
independentes sem configurar um backend remoto.

Uso tipico (dentro de um step):

    tf = TerraformRunner(
        module_source=Path("infra/aws/02-datalake"),
        workspace=ctx.state_dir / "02-datalake",
        env=ctx.credentials.to_env(),
        emit_log=ctx.info,
    )
    await tf.init()
    await tf.apply(vars={"bucket_name": "foo", "project_name": "bar"})
    outputs = await tf.output()
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import shutil
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

import structlog

logger = structlog.get_logger()

LogFn = Callable[[str], Awaitable[None]]

# Patterns de secrets que podem aparecer no stdout/stderr do terraform.
# Regex conservador: redacta o miolo mantendo prefixo identificavel.
_SECRET_PATTERNS = re.compile(
    r"(AKIA[A-Z0-9])[A-Z0-9]{12,}"  # AWS access key
    r"|([a-zA-Z0-9/+=]{30,})"  # generic long base64 (secret keys)
    r"|(dapi[a-f0-9])[a-f0-9]{20,}"  # Databricks token
    r"|(ghp_[a-zA-Z0-9])[a-zA-Z0-9]{20,}"  # GitHub PAT
    r"|(sk-ant-api[a-zA-Z0-9-])[a-zA-Z0-9-]{20,}",  # Anthropic key
    re.ASCII,
)


def _sanitize_log_line(line: str) -> str:
    """Redacta padroes de secrets conhecidos numa linha de log."""
    return _SECRET_PATTERNS.sub(r"\1\3\4\5***REDACTED***", line)


class TerraformError(RuntimeError):
    """Um comando terraform terminou com exit code != 0."""

    def __init__(self, cmd: list[str], returncode: int, stderr: str):
        self.cmd = cmd
        self.returncode = returncode
        self.stderr = stderr
        super().__init__(
            f"terraform {cmd[1] if len(cmd) > 1 else '?'} falhou "
            f"(exit={returncode}): {stderr.strip()[:400]}"
        )


class TerraformRunner:
    """Wrapper do CLI terraform. Stream de stdout pro emit_log do step."""

    def __init__(
        self,
        *,
        module_source: Path,
        workspace: Path,
        env: dict[str, str],
        emit_log: LogFn,
    ) -> None:
        self.module_source = module_source.resolve()
        self.workspace = workspace.resolve()
        self.env = env
        self.emit_log = emit_log

    async def ensure_workspace(self) -> None:
        """Copia os .tf files do source pra workspace se ainda nao existir."""
        if self.workspace.exists() and any(self.workspace.glob("*.tf")):
            return
        self.workspace.mkdir(parents=True, exist_ok=True)
        if not self.module_source.exists():
            raise FileNotFoundError(
                f"Terraform module source nao existe: {self.module_source}"
            )
        for path in self.module_source.iterdir():
            if path.suffix in {".tf", ".tfvars"} or path.name.endswith(".tf.json"):
                shutil.copy2(path, self.workspace / path.name)
        await self.emit_log(
            f"Workspace preparado: {self.workspace} (copiado de {self.module_source.name})"
        )

    async def init(self) -> None:
        await self.ensure_workspace()
        await self._run(["terraform", "init", "-input=false", "-no-color"])

    async def apply(self, *, tf_vars: dict[str, str] | None = None) -> None:
        args = ["terraform", "apply", "-auto-approve", "-input=false", "-no-color"]
        for key, value in (tf_vars or {}).items():
            args.extend(["-var", f"{key}={value}"])
        await self._run(args)

    async def destroy(self, *, tf_vars: dict[str, str] | None = None) -> None:
        args = ["terraform", "destroy", "-auto-approve", "-input=false", "-no-color"]
        for key, value in (tf_vars or {}).items():
            args.extend(["-var", f"{key}={value}"])
        await self._run(args)

    async def output(self) -> dict[str, Any]:
        """Retorna `terraform output -json` como dict."""
        stdout = await self._run(
            ["terraform", "output", "-json", "-no-color"], capture=True
        )
        if not stdout.strip():
            return {}
        try:
            parsed = json.loads(stdout)
        except json.JSONDecodeError as exc:
            raise TerraformError(
                ["terraform", "output"], 0, f"output json invalido: {exc}"
            ) from exc
        # terraform output -json retorna {key: {value, type, sensitive}}
        return {k: v.get("value") for k, v in parsed.items()}

    async def _run(self, cmd: list[str], *, capture: bool = False) -> str:
        """Executa um comando terraform e streama stdout/stderr pro emit_log.

        Se `capture=True`, retorna stdout acumulado (usado pelo `output()`).
        """
        # Env minimo: so PATH/HOME/TMP do parent + credenciais explicitas.
        # Evita vazar env vars do parent process pro subprocess.
        minimal_parent = {
            k: v
            for k, v in os.environ.items()
            if k in ("PATH", "HOME", "USERPROFILE", "TMP", "TEMP", "SYSTEMROOT", "COMSPEC")
        }
        env = {**minimal_parent, **self.env}
        logger.info("terraform command", cmd=cmd, cwd=str(self.workspace))

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            cwd=str(self.workspace),
            env=env,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        stdout_chunks: list[str] = []
        stderr_chunks: list[str] = []

        async def _pump(stream: asyncio.StreamReader | None, sink: list[str]) -> None:
            if stream is None:
                return
            while True:
                line_bytes = await stream.readline()
                if not line_bytes:
                    break
                line = line_bytes.decode(errors="replace").rstrip()
                if not line:
                    continue
                sink.append(line)
                if not capture:
                    await self.emit_log(f"[tf] {_sanitize_log_line(line)}")

        await asyncio.gather(
            _pump(proc.stdout, stdout_chunks),
            _pump(proc.stderr, stderr_chunks),
        )
        returncode = await proc.wait()

        stdout = "\n".join(stdout_chunks)
        stderr = "\n".join(stderr_chunks)

        if returncode != 0:
            # stderr pode estar vazio — anexa ultimas linhas do stdout pra contexto.
            # Sanitiza antes de incluir no TerraformError (que pode viajar pro SSE).
            raw_detail = stderr or "\n".join(stdout_chunks[-20:])
            detail = _sanitize_log_line(raw_detail)
            raise TerraformError(cmd, returncode, detail)

        return stdout
