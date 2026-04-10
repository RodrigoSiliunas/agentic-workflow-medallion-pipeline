"""Testes unitarios para carga e validacao do ObserverConfig."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from pipeline_lib.agent.observer.config import (
    ObserverConfig,
    load_observer_config,
)

# ================================================================
# ObserverConfig (Pydantic model)
# ================================================================


class TestObserverConfigDefaults:
    def test_default_values(self):
        config = ObserverConfig()
        assert config.llm_provider == "anthropic"
        assert config.llm_model == "claude-opus-4-20250514"
        assert config.llm_max_tokens == 16000
        assert config.git_provider == "github"
        assert config.base_branch == "dev"
        assert config.max_retries == 3
        assert config.dedup_window_hours == 24
        assert config.dry_run is False
        assert config.confidence_threshold == 0.0
        assert config.max_tokens_per_day == 0

    def test_extra_fields_rejected(self):
        with pytest.raises(ValidationError):
            ObserverConfig(unknown_field="x")

    def test_negative_retries_rejected(self):
        with pytest.raises(ValidationError):
            ObserverConfig(max_retries=-1)

    def test_negative_window_rejected(self):
        with pytest.raises(ValidationError):
            ObserverConfig(dedup_window_hours=-5)

    def test_confidence_out_of_range_rejected(self):
        with pytest.raises(ValidationError):
            ObserverConfig(confidence_threshold=1.5)
        with pytest.raises(ValidationError):
            ObserverConfig(confidence_threshold=-0.1)

    def test_zero_max_tokens_rejected(self):
        with pytest.raises(ValidationError):
            ObserverConfig(llm_max_tokens=0)

    def test_dry_run_coerced_from_string(self):
        assert ObserverConfig(dry_run="true").dry_run is True
        assert ObserverConfig(dry_run="false").dry_run is False
        assert ObserverConfig(dry_run="yes").dry_run is True
        assert ObserverConfig(dry_run="1").dry_run is True
        assert ObserverConfig(dry_run="no").dry_run is False


# ================================================================
# load_observer_config — YAML
# ================================================================


class TestLoadYaml:
    def test_load_from_yaml_with_observer_section(self, tmp_path: Path):
        config_file = tmp_path / "observer_config.yaml"
        config_file.write_text(
            "observer:\n"
            "  llm_provider: openai\n"
            "  llm_model: gpt-4o\n"
            "  dedup_window_hours: 48\n"
            "  dry_run: true\n",
            encoding="utf-8",
        )

        config = load_observer_config(config_path=config_file)

        assert config.llm_provider == "openai"
        assert config.llm_model == "gpt-4o"
        assert config.dedup_window_hours == 48
        assert config.dry_run is True
        # Campos nao definidos mantem defaults
        assert config.max_retries == 3
        assert config.base_branch == "dev"

    def test_load_from_yaml_flat(self, tmp_path: Path):
        config_file = tmp_path / "observer_config.yaml"
        config_file.write_text(
            "llm_provider: openai\n"
            "dedup_window_hours: 12\n",
            encoding="utf-8",
        )

        config = load_observer_config(config_path=config_file)

        assert config.llm_provider == "openai"
        assert config.dedup_window_hours == 12

    def test_missing_file_uses_defaults(self, tmp_path: Path):
        config = load_observer_config(
            config_path=tmp_path / "does_not_exist.yaml"
        )
        # Tudo default
        assert config.llm_provider == "anthropic"
        assert config.dedup_window_hours == 24

    def test_none_config_path_uses_defaults(self):
        config = load_observer_config(config_path=None)
        assert config.llm_provider == "anthropic"

    def test_invalid_yaml_falls_back_to_defaults(self, tmp_path: Path):
        bad = tmp_path / "bad.yaml"
        bad.write_text("not: valid: yaml: here:\n  - x\n- z", encoding="utf-8")

        # Falha de parse eh logada e retorna defaults
        config = load_observer_config(config_path=bad)
        assert config.llm_provider == "anthropic"


# ================================================================
# load_observer_config — JSON
# ================================================================


class TestLoadJson:
    def test_load_from_json(self, tmp_path: Path):
        config_file = tmp_path / "observer_config.json"
        config_file.write_text(
            json.dumps(
                {
                    "observer": {
                        "llm_provider": "openai",
                        "llm_model": "gpt-4o",
                        "confidence_threshold": 0.7,
                    }
                }
            ),
            encoding="utf-8",
        )

        config = load_observer_config(config_path=config_file)

        assert config.llm_provider == "openai"
        assert config.confidence_threshold == 0.7


# ================================================================
# Overrides (widgets)
# ================================================================


class TestOverrides:
    def test_widgets_override_yaml(self, tmp_path: Path):
        config_file = tmp_path / "observer_config.yaml"
        config_file.write_text(
            "observer:\n"
            "  llm_provider: anthropic\n"
            "  dedup_window_hours: 24\n"
            "  dry_run: false\n",
            encoding="utf-8",
        )

        config = load_observer_config(
            config_path=config_file,
            overrides={
                "llm_provider": "openai",
                "dedup_window_hours": "72",
                "dry_run": "true",
            },
        )

        assert config.llm_provider == "openai"
        assert config.dedup_window_hours == 72
        assert config.dry_run is True

    def test_empty_overrides_keep_yaml(self, tmp_path: Path):
        config_file = tmp_path / "observer_config.yaml"
        config_file.write_text(
            "observer:\n  llm_provider: openai\n",
            encoding="utf-8",
        )

        # Widget vazio = ignora o override (nao sobrescreve YAML)
        config = load_observer_config(
            config_path=config_file,
            overrides={"llm_provider": "", "dedup_window_hours": "  "},
        )

        assert config.llm_provider == "openai"
        assert config.dedup_window_hours == 24  # default

    def test_none_overrides_are_ignored(self):
        config = load_observer_config(
            overrides={"llm_provider": None},
        )
        assert config.llm_provider == "anthropic"

    def test_invalid_override_key_is_skipped(self):
        # Override com key desconhecida eh logado e ignorado (nao crash)
        config = load_observer_config(
            overrides={"unknown_field": "x", "llm_provider": "openai"},
        )
        assert config.llm_provider == "openai"

    def test_int_override_coercion(self):
        config = load_observer_config(
            overrides={"dedup_window_hours": "48", "max_retries": "5"},
        )
        assert config.dedup_window_hours == 48
        assert config.max_retries == 5

    def test_invalid_int_override_falls_back(self):
        # Widget com valor nao-numerico eh ignorado
        config = load_observer_config(
            overrides={"dedup_window_hours": "abc"},
        )
        assert config.dedup_window_hours == 24  # default

    def test_float_override_coercion(self):
        config = load_observer_config(
            overrides={"confidence_threshold": "0.75"},
        )
        assert config.confidence_threshold == 0.75


# ================================================================
# Hierarquia: overrides > yaml > defaults
# ================================================================


class TestHierarchy:
    def test_all_three_layers(self, tmp_path: Path):
        config_file = tmp_path / "observer_config.yaml"
        # YAML define alguns campos
        config_file.write_text(
            "observer:\n"
            "  llm_provider: openai\n"
            "  dedup_window_hours: 12\n",
            encoding="utf-8",
        )

        # Widgets sobrescrevem apenas 1 campo do YAML
        config = load_observer_config(
            config_path=config_file,
            overrides={"dedup_window_hours": "48"},
        )

        # Widget override
        assert config.dedup_window_hours == 48
        # YAML value
        assert config.llm_provider == "openai"
        # Default value (nao definido em nenhum lugar)
        assert config.max_retries == 3
        assert config.base_branch == "dev"
