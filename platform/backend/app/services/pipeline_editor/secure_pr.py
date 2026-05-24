"""Validação e PR seguro para edições do Pipeline Editor."""

from __future__ import annotations

import difflib

from observer import validate_fix

from app.services.pipeline_editor.codegen import generate_pyspark_patch
from app.services.pipeline_editor.manifest import PipelineManifest
from app.services.pipeline_editor.schemas import TransformDraft


def build_code_diff(
    *,
    source_by_path: dict[str, str],
    generated_files: dict[str, str],
) -> list[dict]:
    """Gera diff unificado por arquivo (source vs generated)."""
    diffs: list[dict] = []
    for path, new_content in generated_files.items():
        old_content = source_by_path.get(path, "")
        patch_lines = difflib.unified_diff(
            old_content.splitlines(keepends=True),
            new_content.splitlines(keepends=True),
            fromfile=f"a/{path}",
            tofile=f"b/{path}",
        )
        patch = "".join(patch_lines)
        additions = sum(
            1
            for line in patch.splitlines()
            if line.startswith("+") and not line.startswith("+++")
        )
        deletions = sum(
            1
            for line in patch.splitlines()
            if line.startswith("-") and not line.startswith("---")
        )
        diffs.append(
            {
                "path": path,
                "additions": additions,
                "deletions": deletions,
                "patch": patch,
            }
        )
    return diffs


def validate_generated_files(
    *,
    source_by_path: dict[str, str],
    draft: TransformDraft,
    manifest: PipelineManifest,
) -> tuple[dict[str, str], dict]:
    node = manifest.resolve_node(draft.target_node)
    source = source_by_path.get(node.file_path)
    if source is None:
        raise ValueError(f"Arquivo base ausente para codegen: {node.file_path}")

    generated = {node.file_path: generate_pyspark_patch(source, draft, node=node)}
    checks: list[str] = []
    errors: list[str] = []
    for path, code in generated.items():
        result = validate_fix(code=code, file_path=path)
        checks.extend(result.checks_run)
        if not result.valid:
            errors.extend(result.errors)
    validation = {
        "valid": not errors,
        "checks": sorted(set(checks)),
        "errors": errors,
    }
    return generated, validation
