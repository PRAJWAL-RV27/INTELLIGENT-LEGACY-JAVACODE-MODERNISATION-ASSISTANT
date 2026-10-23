"""
Performance-aware Java 21 optimization package.
"""

from .performance_analyzer import (
    BenchmarkResult,
    PerformanceAnalyzer,
)

from .optional_optimizer import (
    OptimizationResult,
    OptionalOptimizer,
)

from .optimizer_pipeline import (
    OptionalOptimizationPipeline,
    PipelineResult,
)

__all__ = [
    "BenchmarkResult",
    "PerformanceAnalyzer",
    "OptimizationResult",
    "OptionalOptimizer",
    "OptionalOptimizationPipeline",
    "PipelineResult",
]