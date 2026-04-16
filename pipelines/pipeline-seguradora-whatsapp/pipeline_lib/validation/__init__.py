"""Helpers de validação/metricas O(1) baseadas em Delta transaction log."""

from pipeline_lib.validation.delta_stats import delta_row_count

__all__ = ["delta_row_count"]
