"""
optimizer_pipeline.py

Runs optional Java 21 transformations through the performance-aware
decision engine.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Collection, Optional

from .optional_optimizer import (
    OptionalOptimizer,
    OptimizationResult,
)
from .optional_transformers import OPTIONAL_TRANSFORMERS


@dataclass
class PipelineResult:
    source: str
    results: list[OptimizationResult]


class OptionalOptimizationPipeline:
    """
    Executes optional transformations one at a time.

    A transformation is kept only when the performance optimizer
    accepts it.
    """

    def __init__(
        self,
        min_runtime_improvement_percent: float = 5.0,
        min_memory_improvement_percent: float = 0.0,
        target_java_version: int = 21,
        enabled_transformers: Optional[Collection[str]] = None,
    ) -> None:

        self.optimizer = OptionalOptimizer(
            min_runtime_improvement_percent=(
                min_runtime_improvement_percent
            ),
            min_memory_improvement_percent=(
                min_memory_improvement_percent
            ),
        )

        allowed = set(enabled_transformers) if enabled_transformers is not None else None
        configured = []
        seen_names: set[str] = set()
        for transformer in OPTIONAL_TRANSFORMERS:
            name = getattr(transformer, "NAME", type(transformer).__name__)
            if name in seen_names:
                continue
            if allowed is not None and name not in allowed:
                continue
            configure = getattr(transformer, "configure", None)
            if configure is not None:
                configure(target_java_version=target_java_version)
            seen_names.add(name)
            configured.append(transformer)

        self.target_java_version = target_java_version
        self.transformers = configured

    def transform(
        self,
        source: str,
        filename: str = "",
    ) -> PipelineResult:

        current_source = source
        results: list[OptimizationResult] = []

        for transformer in self.transformers:

            # ----------------------------------------------------------
            # Generate the candidate using the optional transformer.
            # ----------------------------------------------------------

            candidate_source, changes = transformer.transform(
                current_source
            )

            # No candidate was found.
            if not changes:
                continue

            # ----------------------------------------------------------
            # The transformer has already established its conservative
            # semantic-safety conditions.
            #
            # Now the performance optimizer decides whether to keep it.
            # ----------------------------------------------------------

            def candidate_transform(
                _source: str,
                candidate=candidate_source,
            ) -> str:
                return candidate

            if getattr(transformer, "requires_performance_evaluation", True) is False:
                result = OptimizationResult(
                    applied=True,
                    candidate_name=transformer.NAME,
                    original_source=current_source,
                    final_source=candidate_source,
                    reason=(
                        "Semantic-only modernization applied for target "
                        f"Java {self.target_java_version}."
                    ),
                    details=changes,
                )
                results.append(result)
                current_source = candidate_source
                continue

            result = self.optimizer.optimize(
                source_code=current_source,
                candidate_name=transformer.NAME,
                transform=candidate_transform,
                filename=filename,
            )

            results.append(result)

            if result.applied:
                current_source = result.final_source

        return PipelineResult(
            source=current_source,
            results=results,
        )