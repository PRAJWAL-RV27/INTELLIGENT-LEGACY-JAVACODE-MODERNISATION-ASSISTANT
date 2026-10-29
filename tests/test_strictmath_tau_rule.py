from __future__ import annotations

import sys
from pathlib import Path

import pytest
import subprocess
import tempfile
import shutil

ROOT = Path(__file__).resolve().parents[1]
FILES = ROOT / "files"
if str(FILES) not in sys.path:
    sys.path.insert(0, str(FILES))

from optimizer.optimizer_pipeline import OptionalOptimizationPipeline
from transformers.strictmath_tau_transform import StrictMathTauTransformer


@pytest.mark.parametrize(
    ("expression", "expected"),
    [
        ("2 * StrictMath.PI", "StrictMath.TAU"),
        ("StrictMath.PI * 2", "StrictMath.TAU"),
        ("2.0 * StrictMath.PI", "StrictMath.TAU"),
        ("StrictMath.PI * 2f", "StrictMath.TAU"),
        ("(2L) * (StrictMath.PI)", "StrictMath.TAU"),
    ],
)
def test_direct_reversed_literal_and_parenthesized(expression: str,
                                                    expected: str) -> None:
    source = f"class Example {{ double value = {expression}; }}"
    transformed, changes = StrictMathTauTransformer().transform(source)

    assert expected in transformed
    assert "StrictMath.PI" not in transformed
    assert len(changes) == 1


def test_verified_exact_static_import() -> None:
    source = """
import static java.lang.StrictMath.PI;
class Example { double fullTurn = 2 * PI; }
"""
    transformed, changes = StrictMathTauTransformer().transform(source)

    assert "double fullTurn = StrictMath.TAU;" in transformed
    assert len(changes) == 1


def test_verified_wildcard_static_import() -> None:
    source = """
import static java.lang.StrictMath.*;
class Example { double fullTurn = PI * 2.0; }
"""
    transformed, changes = StrictMathTauTransformer().transform(source)

    assert "double fullTurn = StrictMath.TAU;" in transformed
    assert len(changes) == 1


@pytest.mark.parametrize(
    "source",
    [
        "class Example { double value = 2 * Math.PI; }",
        "class Example { static final double PI = 3.14; double x = 2 * PI; }",
        "class Example { double PI = 3.14; void m(double PI) { double x = PI * 2; } }",
        "import static example.Custom.PI; class Example { double x = 2 * PI; }",
    ],
)
def test_unrelated_custom_and_unsupported_sources_are_not_changed(source: str) -> None:
    transformed, changes = StrictMathTauTransformer().transform(source)
    assert transformed == source
    assert changes == []


def test_comments_strings_and_additional_operands_are_safe() -> None:
    source = '''
class Example {
    String text = "2 * StrictMath.PI";
    // 2 * StrictMath.PI
    double x = sideEffect() * (2 /* exact factor */ * StrictMath.PI);
    double y = StrictMath.PI * 2 / 3;
}
'''
    transformed, changes = StrictMathTauTransformer().transform(source)

    assert 'String text = "2 * StrictMath.PI";' in transformed
    assert "// 2 * StrictMath.PI" in transformed
    assert "sideEffect() * (/* exact factor */ StrictMath.TAU)" in transformed
    assert "StrictMath.TAU / 3" in transformed
    assert len(changes) == 2


def test_comments_between_operator_and_pi_are_preserved() -> None:
    source = "class Example { double x = 2 /* keep */ * StrictMath.PI; }"
    transformed, changes = StrictMathTauTransformer().transform(source)

    assert "/* keep */ StrictMath.TAU" in transformed
    assert len(changes) == 1


@pytest.mark.parametrize("target", [8, 18])
def test_target_below_java_19_is_skipped(target: int) -> None:
    source = "class Example { double x = 2 * StrictMath.PI; }"
    transformed, changes = StrictMathTauTransformer(target).transform(source)
    assert transformed == source
    assert changes == []


def test_java_19_or_later_is_transformed() -> None:
    source = "class Example { double x = 2 * StrictMath.PI; }"
    transformed, changes = StrictMathTauTransformer(19).transform(source)
    assert "StrictMath.TAU" in transformed
    assert len(changes) == 1


def test_disabled_configuration_is_skipped() -> None:
    source = "class Example { double x = 2 * StrictMath.PI; }"
    transformed, changes = StrictMathTauTransformer(enabled=False).transform(source)
    assert transformed == source
    assert changes == []


def test_idempotency() -> None:
    source = "class Example { double x = 2 * StrictMath.PI; }"
    once, first_changes = StrictMathTauTransformer().transform(source)
    twice, second_changes = StrictMathTauTransformer().transform(once)

    assert twice == once
    assert first_changes
    assert second_changes == []


def test_optional_pipeline_applies_and_reports() -> None:
    source = "class Example { double x = 2 * StrictMath.PI; }"
    pipeline = OptionalOptimizationPipeline(
        target_java_version=21,
        enabled_transformers={"StrictMath.PI doubling -> StrictMath.TAU"},
    )

    result = pipeline.transform(source, "Example.java")

    assert result.source == "class Example { double x = StrictMath.TAU; }"
    assert len(result.results) == 1
    assert result.results[0].applied
    assert result.results[0].details
    assert "line 1" in result.results[0].details[0]


def test_optional_pipeline_target_and_disable_configuration() -> None:
    source = "class Example { double x = 2 * StrictMath.PI; }"

    old_target = OptionalOptimizationPipeline(
        target_java_version=18,
        enabled_transformers={"StrictMath.PI doubling -> StrictMath.TAU"},
    ).transform(source)
    disabled = OptionalOptimizationPipeline(
        target_java_version=21,
        enabled_transformers=set(),
    ).transform(source)

    assert old_target.source == source
    assert old_target.results == []
    assert disabled.source == source
    assert disabled.results == []


def test_transformed_source_compiles_with_javac() -> None:
    javac = shutil.which("javac")
    if javac is None:
        pytest.skip("javac is not installed")

    source = """
public class TauExample {
    public static double fullTurn() { return 2 * StrictMath.PI; }
}
"""
    transformed, _ = StrictMathTauTransformer().transform(source)

    with tempfile.TemporaryDirectory() as directory:
        java_file = Path(directory, "TauExample.java")
        java_file.write_text(transformed, encoding="utf-8")
        completed = subprocess.run(
            [javac, "--release", "21", str(java_file)],
            cwd=directory,
            capture_output=True,
            text=True,
            check=False,
        )

    assert completed.returncode == 0, completed.stderr


def test_transformer_is_registered_once_in_optional_registry() -> None:
    from optimizer.optional_transformers import OPTIONAL_TRANSFORMERS

    matches = [
        transformer for transformer in OPTIONAL_TRANSFORMERS
        if transformer.NAME == "StrictMath.PI doubling -> StrictMath.TAU"
    ]
    assert len(matches) == 1
