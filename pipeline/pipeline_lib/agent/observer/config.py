"""Configuracao do Observer Agent via arquivo YAML/JSON.

Permite versionar a config do Observer no repositorio ao inves de
depender apenas de widgets Databricks. Hierarquia de prioridade:

    1. Overrides (widgets Databricks) — sobrescrevem tudo
    2. Arquivo YAML/JSON no repo (ex: pipeline/observer_config.yaml)
    3. Defaults hardcoded em ObserverConfig (menor prioridade)

Uso:
    from pipeline_lib.agent.observer.config import load_observer_config

    config = load_observer_config(
        config_path="/Workspace/Repos/.../pipeline/observer_config.yaml",
        overrides={"dry_run": "true", "dedup_window_hours": "48"},
    )

    # Acessa campos tipados
    if config.dry_run:
        ...
    window = config.dedup_window_hours
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


def _coerce_bool(value: Any) -> bool:
    """Converte valores comuns de strings para bool.

    Aceita 'true'/'false'/'yes'/'no'/'1'/'0'/'on'/'off' (case-insensitive),
    alem de bool nativo e int. Usado para normalizar dry_run vindo de YAML
    com string explicita ou de widgets Databricks.
    """
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return bool(value)
    if isinstance(value, str):
        return value.strip().lower() in ("true", "yes", "1", "on")
    return bool(value)


class ObserverConfig(BaseModel):
    """Configuracao tipada do Observer Agent.

    Todos os campos tem defaults sensatos — uma instalacao fresca pode rodar
    sem YAML de config. Widgets Databricks podem sobrescrever qualquer campo
    via `load_observer_config(overrides=...)`.

    Compativel com Pydantic V1 (Databricks Runtime) e V2 (dev local).
    """

    # Usa class Config V1-style que eh aceita por ambas as versoes do Pydantic
    class Config:
        extra = "forbid"

    # LLM
    llm_provider: str = Field(
        default="anthropic",
        description="Nome do LLM provider registrado (anthropic, openai, ...)",
    )
    llm_model: str = Field(
        default="claude-opus-4-20250514",
        description="Modelo especifico do LLM provider",
    )
    llm_max_tokens: int = Field(
        default=16000,
        gt=0,
        description="Limite de output tokens por chamada ao LLM",
    )

    # Git
    git_provider: str = Field(
        default="github",
        description="Nome do Git provider registrado (github, gitlab, ...)",
    )
    base_branch: str = Field(
        default="dev",
        description="Branch base para os PRs criados pelo Observer",
    )

    # Resilience
    max_retries: int = Field(
        default=3,
        ge=0,
        description="Numero de retries em chamadas a LLM/Git providers",
    )

    # Dedup
    dedup_window_hours: int = Field(
        default=24,
        ge=0,
        description="Janela em horas para considerar um diagnostico duplicado",
    )

    # Operacional
    dry_run: bool = Field(
        default=False,
        description="Se true, diagnostica mas nao cria PRs (apenas loga e persiste)",
    )
    confidence_threshold: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Confianca minima para criar PR (0.0 = sempre cria)",
    )
    max_tokens_per_day: int = Field(
        default=0,
        ge=0,
        description="Limite diario de tokens (0 = sem limite). Nao usado hoje, reservado.",
    )


def _coerce_override_value(field_name: str, value: Any) -> Any:
    """Converte strings de widgets para o tipo esperado pelo campo Pydantic.

    Widgets Databricks sempre retornam strings. Para manter a hierarquia
    funcional (widgets > YAML > defaults) precisamos converter 'true' para
    True, '24' para 24, etc. antes de entregar ao Pydantic.
    """
    if value is None:
        return None
    if not isinstance(value, str):
        return value

    stripped = value.strip()
    if stripped == "":
        return None  # Widget vazio = ignora o override

    if field_name in {"llm_max_tokens", "max_retries", "dedup_window_hours", "max_tokens_per_day"}:
        try:
            return int(stripped)
        except ValueError:
            logger.warning(f"override '{field_name}={value}' nao e inteiro — ignorando")
            return None

    if field_name == "confidence_threshold":
        try:
            return float(stripped)
        except ValueError:
            logger.warning(f"override '{field_name}={value}' nao e float — ignorando")
            return None

    if field_name == "dry_run":
        return _coerce_bool(stripped)

    return stripped


def _read_config_file(path: Path) -> dict[str, Any]:
    """Le YAML ou JSON do filesystem e retorna o dict bruto.

    Suporta nested (chave 'observer:') ou flat (campos no topo).
    """
    raw = path.read_text(encoding="utf-8")
    suffix = path.suffix.lower()

    if suffix in (".yaml", ".yml"):
        try:
            import yaml
        except ImportError as exc:
            raise ImportError(
                "Para ler observer_config.yaml instale pyyaml (pip install pyyaml)"
            ) from exc
        data = yaml.safe_load(raw) or {}
    elif suffix == ".json":
        data = json.loads(raw) if raw.strip() else {}
    else:
        raise ValueError(
            f"Extensao nao suportada: {suffix} (use .yaml, .yml ou .json)"
        )

    if not isinstance(data, dict):
        raise ValueError(
            f"Config {path} deve ser um mapping no topo, recebido {type(data).__name__}"
        )

    # Suporta arquivo com secao 'observer:' encapsulando a config
    if "observer" in data and isinstance(data["observer"], dict):
        result = data["observer"]
    else:
        result = data

    # Coerce dry_run para bool caso venha como string no YAML (defensivo —
    # pyyaml ja retorna bool para `dry_run: true`, mas aceitamos `dry_run: "true"`)
    if "dry_run" in result:
        result["dry_run"] = _coerce_bool(result["dry_run"])

    return result


def load_observer_config(
    config_path: str | Path | None = None,
    overrides: dict[str, Any] | None = None,
) -> ObserverConfig:
    """Carrega ObserverConfig combinando YAML/JSON + overrides + defaults.

    Args:
        config_path: caminho absoluto do arquivo YAML/JSON. Se None ou o
            arquivo nao existir, usa so defaults + overrides.
        overrides: dict com valores vindos de widgets (strings). Valores
            None ou vazios sao ignorados para preservar o YAML/defaults.

    Returns:
        ObserverConfig validado via Pydantic.

    Raises:
        pydantic.ValidationError: se algum campo apos o merge ficar invalido.
    """
    merged: dict[str, Any] = {}

    if config_path is not None:
        path = Path(config_path)
        if path.exists():
            try:
                file_data = _read_config_file(path)
                merged.update(file_data)
                logger.info(f"Observer config carregada de {path}")
            except Exception as exc:
                logger.warning(
                    f"Falha ao ler config {path}: {exc}. Usando defaults."
                )
        else:
            logger.info(f"Config file {path} nao encontrado — usando defaults")

    if overrides:
        valid_fields = set(ObserverConfig.model_fields.keys())
        for key, value in overrides.items():
            if key not in valid_fields:
                logger.warning(f"override '{key}' nao eh campo valido de ObserverConfig")
                continue
            coerced = _coerce_override_value(key, value)
            if coerced is None:
                continue  # Ignora overrides vazios
            merged[key] = coerced

    return ObserverConfig(**merged)
