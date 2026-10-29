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
from transformers.math_abs_exact_transform import MathAbsExactTransformer


def test_guarded_math_abs_is_modernized() -> None:
    source = """
class Example {
    int magnitude(int value) {
        if (value == Integer.MIN_VALUE) throw new ArithmeticException();
        return Math.abs(value);
    }
}
"""
    transformed, changes = MathAbsExactTransformer().transform(source)

    assert "return Math.absExact(value);" in transformed
    assert changes
    assert "Integer.MIN_VALUE" in changes[0]


def test_braced_guard_and_qualified_min_are_supported() -> None:
    source = """
class Example {
    int magnitude(int value) {
        if (value == java.lang.Integer.MIN_VALUE) {
            throw new ArithmeticException("overflow");
        }
        int result = Math.abs(value);
        return result;
    }
}
"""
    transformed, changes = MathAbsExactTransformer().transform(source)

    assert "int result = Math.absExact(value);" in transformed
    assert len(changes) == 1


def test_comments_and_strings_are_untouched() -> None:
    source = '''
class Example {
    // if (value == Integer.MIN_VALUE) throw new ArithmeticException();
    String text = "Math.abs(value)";
    int magnitude(int value) {
        if (value == Integer.MIN_VALUE) throw new ArithmeticException();
        return /* preserve */ Math.abs(value);
    }
}
'''
    transformed, changes = MathAbsExactTransformer().transform(source)

    assert "// if (value == Integer.MIN_VALUE)" in transformed
    assert 'String text = "Math.abs(value)";' in transformed
    assert "return /* preserve */ Math.absExact(value);" in transformed
    assert len(changes) == 1


@pytest.mark.parametrize(
    "source",
    [
        "class E { int f(int x) { return Math.abs(x); } }",
        "class E { int f(int x) { if (x == Integer.MIN_VALUE) return -1; return Math.abs(x); } }",
        "class E { int f(int x) { if (x == Integer.MIN_VALUE) throw new IllegalArgumentException(); return Math.abs(x); } }",
        "class E { int f(int x) { if (other == Integer.MIN_VALUE) throw new ArithmeticException(); return Math.abs(x); } }",
        "class E { int f(int x) { if (x == Integer.MAX_VALUE) throw new ArithmeticException(); return Math.abs(x); } }",
        "class E { int f(int x) { if (x == Integer.MIN_VALUE) throw new ArithmeticException(); return StrictMath.abs(x); } }",
        "class E { int f(int x) { if (x == Integer.MIN_VALUE) throw new ArithmeticException(); return Math.abs(x + 1); } }",
        "class E { int f(int x) { if (x == Integer.MIN_VALUE) throw new ArithmeticException(); doSomething(); return Math.abs(x); } }",
    ],
)
def test_unsupported_or_unproven_patterns_are_unchanged(source: str) -> None:
    transformed, changes = MathAbsExactTransformer().transform(source)
    assert transformed == source
    assert changes == []


@pytest.mark.parametrize("target", [8, 14])
def test_targets_before_java_15_are_skipped(target: int) -> None:
    source = "class E { int f(int x) { if (x == Integer.MIN_VALUE) throw new ArithmeticException(); return Math.abs(x); } }"
    transformed, changes = MathAbsExactTransformer(target).transform(source)
    assert transformed == source
    assert changes == []


def test_disabled_and_java_15_configuration() -> None:
    source = "class E { int f(int x) { if (x == Integer.MIN_VALUE) throw new ArithmeticException(); return Math.abs(x); } }"

    disabled, disabled_changes = MathAbsExactTransformer(enabled=False).transform(source)
    java15, java15_changes = MathAbsExactTransformer(15).transform(source)

    assert disabled == source
    assert disabled_changes == []
    assert "Math.absExact" in java15
    assert java15_changes


def test_idempotency() -> None:
    source = "class E { int f(int x) { if (x == Integer.MIN_VALUE) throw new ArithmeticException(); return Math.abs(x); } }"
    once, changes = MathAbsExactTransformer().transform(source)
    twice, second_changes = MathAbsExactTransformer().transform(once)

    assert once != source
    assert twice == once
    assert changes
    assert second_changes == []


def test_minimum_value_semantics_are_exact() -> None:
    source = """
class AbsExample {
    static int magnitude(int value) {
        if (value == Integer.MIN_VALUE) throw new ArithmeticException();
        return Math.abs(value);
    }
    public static void main(String[] args) {
        System.out.println(magnitude(-7));
        try {
            magnitude(Integer.MIN_VALUE);
            System.out.println("NO_EXCEPTION");
        } catch (ArithmeticException expected) {
            System.out.println("ArithmeticException");
        }
    }
}
"""
    transformed, _ = MathAbsExactTransformer().transform(source)
    javac = shutil.which("javac")
    java = shutil.which("java")
    if javac is None or java is None:
        pytest.skip("javac/java are not installed")

    with tempfile.TemporaryDirectory() as directory:
        Path(directory, "AbsExample.java").write_text(transformed, encoding="utf-8")
        compile_result = subprocess.run(
            [javac, "--release", "21", "AbsExample.java"], cwd=directory,
            capture_output=True, text=True, check=False,
        )
        assert compile_result.returncode == 0, compile_result.stderr
        run_result = subprocess.run(
            [java, "AbsExample"], cwd=directory,
            capture_output=True, text=True, check=False,
        )

    assert run_result.returncode == 0, run_result.stderr
    assert run_result.stdout.splitlines() == ["7", "ArithmeticException"]


def test_optional_pipeline_integration_and_configuration() -> None:
    name = MathAbsExactTransformer.NAME
    source = "class E { int f(int x) { if (x == Integer.MIN_VALUE) throw new ArithmeticException(); return Math.abs(x); } }"

    applied = OptionalOptimizationPipeline(
        target_java_version=21,
        enabled_transformers={name},
    ).transform(source)
    skipped = OptionalOptimizationPipeline(
        target_java_version=14,
        enabled_transformers={name},
    ).transform(source)
    disabled = OptionalOptimizationPipeline(
        target_java_version=21,
        enabled_transformers=set(),
    ).transform(source)

    assert "Math.absExact(x)" in applied.source
    assert len(applied.results) == 1 and applied.results[0].applied
    assert skipped.source == source and skipped.results == []
    assert disabled.source == source and disabled.results == []


def test_registered_exactly_once() -> None:
    matches = [item for item in OPTIONAL_TRANSFORMERS
               if item.NAME == MathAbsExactTransformer.NAME]
    assert len(matches) == 1
