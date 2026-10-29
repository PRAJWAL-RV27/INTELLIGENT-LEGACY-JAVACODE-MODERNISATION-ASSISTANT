"""Conservative modernization of proven integer ceiling-division expressions.

The familiar ``(x + d - 1) / d`` form is not safe in general:

* ``x + d - 1`` can overflow;
* it produces ordinary truncating division, not ceiling division for negative
  dividends; and
* Java's ``ceilDiv`` differs from that formula for negative divisors.

This repository has no Java AST/type checker.  Accordingly, the transformer
only accepts expressions whose divisor is a positive integer constant and
whose dividend is a non-negative integer constant small enough that the
original ``x + d - 1`` cannot overflow.  This can be proved exactly from
literal values, without guessing Java types or symbol scope.
"""
from __future__ import annotations

import re


_DIVISION = re.compile(
    r"\(\s*(?P<dividend>\d+)\s*\+\s*(?P<divisor>\d+)\s*-\s*1\s*\)"
    r"\s*/\s*(?P=divisor)\b"
)
_NO_PAREN = re.compile(
    r"(?<![\w$.])(?P<dividend>\d+)\s*\+\s*(?P<divisor>\d+)\s*-\s*1"
    r"\s*/\s*(?P=divisor)\b"
)


def _mask(source: str) -> str:
    """Mask comments/literals while retaining the same offsets."""
    output: list[str] = []
    i = 0
    length = len(source)
    while i < length:
        char = source[i]
        following = source[i + 1] if i + 1 < length else ""
        if char == "/" and following == "/":
            end = source.find("\n", i)
            end = length if end == -1 else end
            output.append(" " * (end - i))
            i = end
        elif char == "/" and following == "*":
            end = source.find("*/", i + 2)
            end = length if end == -1 else end + 2
            output.append("".join("\n" if item == "\n" else " "
                                  for item in source[i:end]))
            i = end
        elif source.startswith('"""', i):
            end = source.find('"""', i + 3)
            end = length if end == -1 else end + 3
            output.append('"""' + "".join("\n" if item == "\n" else " "
                                           for item in source[i + 3:end - 3])
                          + '"""')
            i = end
        elif char in "\"'":
            end = i + 1
            while end < length and source[end] != char:
                if source[end] == "\\" and end + 1 < length:
                    end += 2
                else:
                    end += 1
            end = min(end + 1, length)
            output.append(char + "_" * max(0, end - i - 2)
                          + (source[end - 1] if end > i + 1 else ""))
            i = end
        else:
            output.append(char)
            i += 1
    return "".join(output)


def _literal(text: str) -> int:
    normalized = text.replace("_", "")
    if normalized.lower().endswith("l"):
        normalized = normalized[:-1]
    return int(normalized, 0)


def _safe(match: re.Match[str]) -> bool:
    dividend = _literal(match.group("dividend"))
    divisor = _literal(match.group("divisor"))
    return (
        0 <= dividend <= 2_147_483_647
        and 1 <= divisor <= 2_147_483_647
        and dividend + divisor <= 2_147_483_647
    )


class MathCeilDivTransformer:
    """Replace only arithmetic-proven ``int`` ceiling-division literals."""

    NAME = "Integer ceiling division pattern -> Math.ceilDiv(int,int)"
    requires_performance_evaluation = False

    def __init__(self, target_java_version: int = 21,
                 enabled: bool = True) -> None:
        self.target_java_version = target_java_version
        self.enabled = enabled

    def configure(self, target_java_version: int,
                  enabled: bool = True) -> None:
        self.target_java_version = target_java_version
        self.enabled = enabled

    def transform(self, source: str) -> tuple[str, list[str]]:
        if not self.enabled or self.target_java_version < 18:
            return source, []

        masked = _mask(source)
        edits: list[tuple[int, int, str, str]] = []

        for match in _DIVISION.finditer(masked):
            if not _safe(match):
                continue
            start, end = match.span()
            original = source[start:end]
            before = start - 1
            after = end
            while before >= 0 and source[before].isspace():
                before -= 1
            while after < len(source) and source[after].isspace():
                after += 1
            if (before >= 0 and source[before] == "("
                    and after < len(source) and source[after] == ")"):
                continue
            if "/*" in original or "//" in original:
                continue
            if any(start < previous_end and end > previous_start
                   for previous_start, previous_end, _, _ in edits):
                continue

            dividend = match.group("dividend")
            divisor = match.group("divisor")
            replacement = f"Math.ceilDiv({dividend}, {divisor})"
            line = source.count("\n", 0, start) + 1
            reason = (
                f"line {line}: replaced {original} with {replacement}; "
                "reason=non-negative int literals, positive divisor, and "
                "overflow-free intermediate expression"
            )
            edits.append((start, end, replacement, reason))

        for start, end, replacement, _ in sorted(edits, reverse=True):
            source = source[:start] + replacement + source[end:]

        return source, [reason for _, _, _, reason in edits]
