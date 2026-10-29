from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
FILES = ROOT / "files"
if str(FILES) not in sys.path:
    sys.path.insert(0, str(FILES))

from optimizer.optimizer_pipeline import OptionalOptimizationPipeline
from optimizer.optional_transformers import OPTIONAL_TRANSFORMERS
from transformers.math_ceil_div_transform import MathCeilDivTransformer


@pytest.mark.parametrize(
    ("expression", "replacement"),
    [
        ("(10 + 3 - 1) / 3", "Math.ceilDiv(10, 3)"),
        ("(1 + 1 - 1) / 1", "Math.ceilDiv(1, 1)"),
        ("(0 + 7 - 1) / 7", "Math.ceilDiv(0, 7)"),
    ],
)
def test_proven_literal_ceiling_division(expression: str,
                                         replacement: str) -> None:
    source = f"class Example {{ int x = {expression}; }}"
    transformed, changes = MathCeilDivTransformer().transform(source)

    assert replacement in transformed
    assert changes
    assert "overflow-free" in changes[0]


@pytest.mark.parametrize(
    "source",
    [
        "class E { int x = (items + pageSize - 1) / pageSize; }",
        "class E { int x = (10 + pageSize - 1) / pageSize; }",
        "class E { int x = (-10 + 3 - 1) / 3; }",
        "class E { int x = (10 + 0 - 1) / 0; }",
        "class E { int x = (10 + -3 - 1) / -3; }",
        "class E { int x = (2147483647 + 2 - 1) / 2; }",
        "class E { int x = (2147483647 + 1 - 1) / 1; }",
        "class E { int x = 10 + 3 - 1 / 3; }",
        "class E { int x = ((10 + 3 - 1) / 3) + custom(); }",
        "class E { int x = (10 /* keep */ + 3 - 1) / 3; }",
        "class E { String x = \"(10 + 3 - 1) / 3\"; }",
        "class E { int x = quotient((10 + 3 - 1) / 3); }",
    ],
)
def test_uncertain_or_unsafe_patterns_are_unchanged(source: str) -> None:
    transformed, changes = MathCeilDivTransformer().transform(source)
    assert transformed == source
    assert changes == []


def test_comments_and_strings_are_not_modified() -> None:
    source = '''
class Example {
    // (10 + 3 - 1) / 3
    String text = "(10 + 3 - 1) / 3";
    int pages = (10 + 3 - 1) / 3;
}
'''
    transformed, changes = MathCeilDivTransformer().transform(source)

    assert "// (10 + 3 - 1) / 3" in transformed
    assert '"(10 + 3 - 1) / 3"' in transformed
    assert "int pages = Math.ceilDiv(10, 3);" in transformed
    assert len(changes) == 1


@pytest.mark.parametrize("target", [8, 17])
def test_java_targets_before_18_are_skipped(target: int) -> None:
    source = "class E { int x = (10 + 3 - 1) / 3; }"
    transformed, changes = MathCeilDivTransformer(target).transform(source)
    assert transformed == source
    assert changes == []


def test_java_18_and_configuration() -> None:
    source = "class E { int x = (10 + 3 - 1) / 3; }"

    disabled, disabled_changes = MathCeilDivTransformer(enabled=False).transform(source)
    java18, java18_changes = MathCeilDivTransformer(18).transform(source)

    assert disabled == source and disabled_changes == []
    assert "Math.ceilDiv(10, 3)" in java18
    assert java18_changes


def test_idempotency() -> None:
    source = "class E { int x = (10 + 3 - 1) / 3; }"
    once, changes = MathCeilDivTransformer().transform(source)
    twice, second_changes = MathCeilDivTransformer().transform(once)

    assert once != source
    assert twice == once
    assert changes
    assert second_changes == []


def test_boundaries_and_divisor_cases() -> None:
    cases = [
        ("(2147483647 + 1 - 1) / 1", False),
        ("(2147483646 + 2 - 1) / 2", False),
        ("(2147483647 + 2 - 1) / 2", False),
        ("(0 + 1 - 1) / 1", True),
        ("(-1 + 2 - 1) / 2", False),
        ("(2147483645 + 2 - 1) / 2", True),
    ]
    transformer = MathCeilDivTransformer()
    for expression, should_transform in cases:
        source = f"class E {{ int x = {expression}; }}"
        transformed, changes = transformer.transform(source)
        assert ("Math.ceilDiv" in transformed) is should_transform
        assert bool(changes) is should_transform


def test_original_and_transformed_boundary_behavior() -> None:
    source = """
class CeilExample {
    static int legacy(int dividend, int divisor) {
        return (dividend + divisor - 1) / divisor;
    }
    static int modern(int dividend, int divisor) {
        return Math.ceilDiv(dividend, divisor);
    }
    public static void main(String[] args) {
        int[] dividends = {0, 1, 10, 20};
        int[] divisors = {1, 2, 3, 7};
        for (int dividend : dividends) {
            for (int divisor : divisors) {
                if (dividend + divisor - 1 > 2147483647) continue;
                System.out.println(legacy(dividend, divisor) + ":" + modern(dividend, divisor));
            }
        }
    }
}
"""
    transformed, _ = MathCeilDivTransformer().transform(source)
    javac = shutil.which("javac")
    java = shutil.which("java")
    if javac is None or java is None:
        pytest.skip("javac/java are not installed")

    with tempfile.TemporaryDirectory() as directory:
        Path(directory, "CeilExample.java").write_text(transformed, encoding="utf-8")
        compiled = subprocess.run(
            [javac, "--release", "21", "CeilExample.java"], cwd=directory,
            capture_output=True, text=True, check=False,
        )
        assert compiled.returncode == 0, compiled.stderr
        result = subprocess.run(
            [java, "CeilExample"], cwd=directory,
            capture_output=True, text=True, check=False,
        )

    assert result.returncode == 0, result.stderr
    assert all(line.split(":", 1)[0] == line.split(":", 1)[1]
               for line in result.stdout.splitlines())


def test_optional_pipeline_integration_and_configuration() -> None:
    name = MathCeilDivTransformer.NAME
    source = "class E { int x = (10 + 3 - 1) / 3; }"

    applied = OptionalOptimizationPipeline(
        target_java_version=21,
        enabled_transformers={name},
    ).transform(source)
    skipped = OptionalOptimizationPipeline(
        target_java_version=17,
        enabled_transformers={name},
    ).transform(source)
    disabled = OptionalOptimizationPipeline(
        target_java_version=21,
        enabled_transformers=set(),
    ).transform(source)

    assert "Math.ceilDiv(10, 3)" in applied.source
    assert len(applied.results) == 1 and applied.results[0].applied
    assert skipped.source == source and skipped.results == []
    assert disabled.source == source and disabled.results == []


def test_registered_exactly_once() -> None:
    matches = [item for item in OPTIONAL_TRANSFORMERS
               if item.NAME == MathCeilDivTransformer.NAME]
    assert len(matches) == 1
