"""
optional_optimizer.py

Performance-aware optimizer for optional Java 21 transformations.

Mandatory Java migration rules should NOT use this class.

This optimizer is intended for transformations where:
    1. The transformation is not required for Java 21 compilation.
    2. Semantic safety has already been established by the candidate rule.
    3. The transformed program can be benchmarked.
    4. The measured performance improvement exceeds the configured threshold.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Optional

from .performance_analyzer import (
    BenchmarkResult,
    PerformanceAnalyzer,
)


TransformFunction = Callable[[str], str]


@dataclass
class OptimizationResult:
    """
    Result of an optional optimization attempt.
    """

    applied: bool
    candidate_name: str

    original_source: str
    final_source: str

    original_benchmark: Optional[BenchmarkResult] = None
    candidate_benchmark: Optional[BenchmarkResult] = None

    runtime_improvement_percent: Optional[float] = None
    memory_improvement_percent: Optional[float] = None

    reason: str = ""

    details: list[str] = field(default_factory=list)

    def summary(self) -> str:
        """
        Return a human-readable optimization summary.
        """

        lines = [
            "=" * 60,
            "PERFORMANCE-AWARE JAVA 21 OPTIMIZATION",
            "=" * 60,
            f"Candidate : {self.candidate_name}",
            f"Decision  : "
            f"{'APPLIED' if self.applied else 'SKIPPED'}",
            f"Reason    : {self.reason}",
            "",
        ]

        if self.original_benchmark is not None:
            lines.extend(
                [
                    "Original:",
                    f"  {self.original_benchmark}",
                    "",
                ]
            )

        if self.candidate_benchmark is not None:
            lines.extend(
                [
                    "Candidate:",
                    f"  {self.candidate_benchmark}",
                    "",
                ]
            )

        if self.runtime_improvement_percent is not None:
            lines.append(
                "Runtime improvement: "
                f"{self.runtime_improvement_percent:.2f}%"
            )

        if self.memory_improvement_percent is not None:
            lines.append(
                "Memory improvement: "
                f"{self.memory_improvement_percent:.2f}%"
            )

        if self.details:
            lines.extend(
                [
                    "",
                    "Details:",
                    *[
                        f"  - {detail}"
                        for detail in self.details
                    ],
                ]
            )

        lines.append("=" * 60)

        return "\n".join(lines)


class OptionalOptimizer:
    """
    Applies optional Java 21 transformations only when empirical
    performance measurements demonstrate sufficient improvement.

    IMPORTANT:
        This class should be used AFTER the mandatory Java migration
        pipeline has produced Java 21-compatible source.
    """

    def __init__(
        self,
        analyzer: Optional[PerformanceAnalyzer] = None,
        min_runtime_improvement_percent: float = 5.0,
        min_memory_improvement_percent: float = 0.0,
    ) -> None:

        if min_runtime_improvement_percent < 0:
            raise ValueError(
                "min_runtime_improvement_percent must be >= 0"
            )

        if min_memory_improvement_percent < 0:
            raise ValueError(
                "min_memory_improvement_percent must be >= 0"
            )

        self.analyzer = (
            analyzer
            if analyzer is not None
            else PerformanceAnalyzer()
        )

        self.min_runtime_improvement_percent = (
            min_runtime_improvement_percent
        )

        self.min_memory_improvement_percent = (
            min_memory_improvement_percent
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def optimize(
        self,
        source_code: str,
        candidate_name: str,
        transform: TransformFunction,
        filename: str = "",
    ) -> OptimizationResult:
        """
        Evaluate one optional transformation.

        Args:
            source_code:
                Current Java source.

            candidate_name:
                Human-readable name of the transformation.

            transform:
                Function that receives source and returns candidate source.

            filename:
                Original Java filename.

        Returns:
            OptimizationResult
        """

        # --------------------------------------------------------------
        # Step 1: Generate candidate
        # --------------------------------------------------------------

        try:
            candidate_source = transform(source_code)

        except Exception as exc:
            return OptimizationResult(
                applied=False,
                candidate_name=candidate_name,
                original_source=source_code,
                final_source=source_code,
                reason="Candidate transformation failed.",
                details=[
                    f"{type(exc).__name__}: {exc}"
                ],
            )

        # --------------------------------------------------------------
        # Step 2: Make sure the transformation changed something
        # --------------------------------------------------------------

        if candidate_source == source_code:
            return OptimizationResult(
                applied=False,
                candidate_name=candidate_name,
                original_source=source_code,
                final_source=source_code,
                reason="No matching transformation found.",
            )

        # --------------------------------------------------------------
        # Step 3: Benchmark original
        # --------------------------------------------------------------

        original_result = self.analyzer.benchmark(
            source_code,
            filename,
        )

        if not original_result.success:
            return OptimizationResult(
                applied=False,
                candidate_name=candidate_name,
                original_source=source_code,
                final_source=source_code,
                original_benchmark=original_result,
                reason="Original program could not be benchmarked.",
                details=[
                    original_result.error
                    or "Unknown benchmarking error."
                ],
            )

        # --------------------------------------------------------------
        # Step 4: Benchmark candidate
        # --------------------------------------------------------------

        candidate_result = self.analyzer.benchmark(
            candidate_source,
            filename,
        )

        if not candidate_result.success:
            return OptimizationResult(
                applied=False,
                candidate_name=candidate_name,
                original_source=source_code,
                final_source=source_code,
                original_benchmark=original_result,
                candidate_benchmark=candidate_result,
                reason="Candidate program could not be benchmarked.",
                details=[
                    candidate_result.error
                    or "Unknown benchmarking error."
                ],
            )
                # --------------------------------------------------------------
        # Step 4b: The program must print exactly the same output
        # --------------------------------------------------------------

        if (
            original_result.output_hash is not None
            and candidate_result.output_hash is not None
            and original_result.output_hash
            != candidate_result.output_hash
        ):
            return OptimizationResult(
                applied=False,
                candidate_name=candidate_name,
                original_source=source_code,
                final_source=source_code,
                original_benchmark=original_result,
                candidate_benchmark=candidate_result,
                reason="Program output changed after the transformation.",
                details=[
                    "Original and candidate print different output, "
                    "so the change does not preserve behaviour."
                ],
            )

        # --------------------------------------------------------------
        # Step 5: Calculate improvements
        # --------------------------------------------------------------

        runtime_improvement = self._percentage_improvement(
            original_result.runtime_ms,
            candidate_result.runtime_ms,
        )

        memory_improvement = self._percentage_improvement(
            original_result.memory_mb,
            candidate_result.memory_mb,
        )

        # --------------------------------------------------------------
        # Step 6: Make decision
        # --------------------------------------------------------------
        # A candidate is accepted when it gives a real gain in runtime OR
        # in memory, and does not make the other metric clearly worse.
        REGRESSION_LIMIT = -5.0          # worse than -5% = regression
        MIN_MEMORY_GAIN = max(self.min_memory_improvement_percent, 5.0)

        runtime_gain = (
            runtime_improvement is not None
            and runtime_improvement >= self.min_runtime_improvement_percent
        )
        memory_gain = (
            memory_improvement is not None
            and memory_improvement >= MIN_MEMORY_GAIN
        )
        # Runtime measurements are noisy (several % between runs) while
        # memory is deterministic. So when memory clearly improved, only a
        # LARGE runtime slowdown (worse than -20%) counts as a regression.
        RUNTIME_LIMIT = -20.0 if memory_gain else REGRESSION_LIMIT
        runtime_regressed = (
            runtime_improvement is not None
            and runtime_improvement < RUNTIME_LIMIT
        )
        memory_regressed = (
            memory_improvement is not None
            and memory_improvement < REGRESSION_LIMIT
        )

        runtime_ok = runtime_gain
        memory_ok = not memory_regressed

        if (runtime_gain or memory_gain) and not runtime_regressed and memory_ok:
            runtime_ok = True

        if runtime_ok and memory_ok:
            return OptimizationResult(
                applied=True,
                candidate_name=candidate_name,
                original_source=source_code,
                final_source=candidate_source,
                original_benchmark=original_result,
                candidate_benchmark=candidate_result,
                runtime_improvement_percent=runtime_improvement,
                memory_improvement_percent=memory_improvement,
                reason=(
                    "Measured runtime improvement exceeded "
                    "the configured threshold."
                    if runtime_gain else
                    "Measured memory improvement exceeded "
                    "the configured threshold."
                ),
            )

        # --------------------------------------------------------------
        # Step 7: Reject candidate
        # --------------------------------------------------------------

        details = []

        if runtime_improvement is not None:
            details.append(
                "Runtime improvement "
                f"{runtime_improvement:.2f}% "
                f"< required "
                f"{self.min_runtime_improvement_percent:.2f}%."
            )

        if (
            memory_improvement is not None
            and self.min_memory_improvement_percent > 0
            and not memory_ok
        ):
            details.append(
                "Memory improvement "
                f"{memory_improvement:.2f}% "
                f"< required "
                f"{self.min_memory_improvement_percent:.2f}%."
            )
        if (
            memory_improvement is not None
            and memory_improvement < -5.0
        ):
            details.append(
                "Candidate allocates "
                f"{-memory_improvement:.2f}% more memory."
            )
        return OptimizationResult(
            applied=False,
            candidate_name=candidate_name,
            original_source=source_code,
            final_source=source_code,
            original_benchmark=original_result,
            candidate_benchmark=candidate_result,
            runtime_improvement_percent=runtime_improvement,
            memory_improvement_percent=memory_improvement,
            reason="No sufficient measured performance improvement.",
            details=details,
        )

    # ------------------------------------------------------------------
    # Comparison
    # ------------------------------------------------------------------

    @staticmethod
    def _percentage_improvement(
        original: Optional[float],
        candidate: Optional[float],
    ) -> Optional[float]:
        """
        Calculate percentage improvement.

        For runtime/memory:

            improvement =
                ((original - candidate) / original) * 100

        Positive value = candidate is better.
        Negative value = candidate is worse.
        """

        if original is None or candidate is None:
            return None

        if original <= 0:
            return None

        return (
            (original - candidate)
            / original
        ) * 100.0
