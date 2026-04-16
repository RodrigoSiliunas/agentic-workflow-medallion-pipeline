"""Step registry para o RealSagaRunner (T4 Phase 4).

Espelha o pattern de providers do observer-framework. Cada step
aplica `@register_saga_step("<id>")` e o RealSagaRunner resolve via
`STEP_REGISTRY` ao invés do dict hardcoded em runner.py.

Adicionar novo step = escrever a classe, aplicar o decorator, importar
o módulo em `steps/__init__.py`. Zero edit no runner.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.services.real_saga.base import SagaStep

# Dict id -> classe (não instância). Runner instancia on-demand.
STEP_REGISTRY: dict[str, type[SagaStep]] = {}


def register_saga_step(step_id: str):
    """Decorator que registra um SagaStep no registry global.

    Uso:
        @register_saga_step("s3")
        class S3Step:
            step_id = "s3"
            async def execute(self, ctx): ...

    Idempotente contra redecoração (útil em hot-reload de testes).
    """

    def decorator(cls: type[SagaStep]) -> type[SagaStep]:
        STEP_REGISTRY[step_id] = cls
        # Garante que `cls.step_id` bate com o parametro do decorator
        if not getattr(cls, "step_id", None):
            cls.step_id = step_id  # type: ignore[attr-defined]
        elif cls.step_id != step_id:
            # Desalinhamento entre decorator e atributo = bug dev. Fica
            # com decorator como fonte de verdade mas logga warn.
            import structlog

            structlog.get_logger().warning(
                "saga step_id divergente — decorator vence",
                decorator_id=step_id,
                class_id=cls.step_id,
                cls=cls.__name__,
            )
            cls.step_id = step_id  # type: ignore[attr-defined]
        return cls

    return decorator


def list_registered_steps() -> list[str]:
    return sorted(STEP_REGISTRY.keys())
