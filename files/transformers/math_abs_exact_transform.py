"""Modernize overflow-guarded ``Math.abs(int)`` calls to ``Math.absExact``.

Oracle documents ``java.lang.Math.absExact(int)`` as since Java 15.  It throws
``ArithmeticException`` for ``Integer.MIN_VALUE`` instead of returning that
negative value as ``Math.abs(int)`` does.

This rule intentionally does not rewrite ordinary ``Math.abs`` calls: doing so
would change overflow behavior.  A call is eligible only when an immediately
preceding, simple guard has proved that the same ``int`` variable is not the
minimum value before throwing ``ArithmeticException``.
"""
from __future__ import annotations

import re


_IDENT = r"[A-Za-z_$][A-Za-z0-9_$]*"
_MIN_VALUE = r"(?:java\.lang\.Integer\.MIN_VALUE|Integer\.MIN_VALUE)"
_NEW_EXCEPTION = r"new\s+ArithmeticException\s*\([^;]*\)"


def _mask(source: str) -> str:
    """Mask comments/literals while preserving offsets for source edits."""
    result: list[str] = []
    i = 0
    n = len(source)
    while i < n:
        char = source[i]
        following = source[i + 1] if i + 1 < n else ""
        if char == "/" and following == "/":
            end = source.find("\n", i)
            end = n if end == -1 else end
            result.append(" " * (end - i))
            i = end
        elif char == "/" and following == "*":
            end = source.find("*/", i + 2)
            end = n if end == -1 else end + 2
            result.append("".join("\n" if c == "\n" else " "
                                  for c in source[i:end]))
            i = end
        elif source.startswith('"""', i):
            end = source.find('"""', i + 3)
            end = n if end == -1 else end + 3
            result.append('"""' + "".join("\n" if c == "\n" else " "
                                           for c in source[i + 3:end - 3])
                          + '"""')
            i = end
        elif char in "\"'":
            end = i + 1
            while end < n and source[end] != char:
                if source[end] == "\\" and end + 1 < n:
                    end += 2
                else:
                    end += 1
            end = min(end + 1, n)
            result.append(char + "_" * max(0, end - i - 2)
                          + (source[end - 1] if end > i + 1 else ""))
            i = end
        else:
            result.append(char)
            i += 1
    return "".join(result)


def _line(source: str, offset: int) -> int:
    return source.count("\n", 0, offset) + 1


_GUARD = re.compile(
    rf"\bif\s*\(\s*(?P<var>{_IDENT})\s*==\s*(?P<min>{_MIN_VALUE})\s*\)"
    rf"\s*(?:"
    rf"throw\s+{_NEW_EXCEPTION}\s*;"
    rf"|[{{]\s*throw\s+{_NEW_EXCEPTION}\s*;\s*[}}]"
    rf")\s*",
)
_ABS = re.compile(
    rf"(?<![\w$.])(?P<receiver>Math)\s*\.\s*abs\s*"
    rf"\(\s*(?P<arg>{_IDENT})\s*\)"
)


class MathAbsExactTransformer:
    """Modernize overflow-guarded ``Math.abs(int)`` calls."""

    NAME = "Overflow-guarded Math.abs(int) -> Math.absExact(int)"
    requires_performance_evaluation = False

    def __init__(self, target_java_version: int = 21,
                 enabled: bool = True) -> None:
        self.target_java_version = target_java_version
        self.enabled = enabled

    def configure(self, target_java_version: int,
                  enabled: bool = True) -> None:
        self.target_java_version = target_java_version
        self.enabled = enabled

    def transform(self, content: str) -> tuple[str, list[str]]:
        if not self.enabled or self.target_java_version < 15:
            return content, []

        masked = _mask(content)
        edits: list[tuple[int, int, str]] = []

        for guard in _GUARD.finditer(masked):
            variable = guard.group("var")
            following = guard.end()

            # Only calls in the immediately following statement are eligible.
            # This is intentionally narrow: control flow and evaluation order
            # are not inferred beyond an explicit unconditional throw.
            statement_start = following
            while statement_start < len(masked) and masked[statement_start].isspace():
                statement_start += 1

            statement_end = masked.find(";", statement_start)
            if statement_end < 0:
                continue
            call = _ABS.search(masked, statement_start, statement_end)
            if call is None or call.group("arg") != variable:
                continue

            # Math.abs must occur in a complete expression statement or return,
            # not an expression whose behavior could depend on surrounding
            # arithmetic or method-overload/context changes.
            after = call.end()
            while after < len(masked) and masked[after].isspace():
                after += 1
            if after >= len(masked) or masked[after] not in ";)?,":
                continue

            edits.append((
                call.start("receiver"),
                call.end(),
                f"Math.absExact({variable})",
            ))

        # Applying right-to-left keeps source offsets stable.
        unique: list[tuple[int, int, str]] = []
        for edit in sorted(edits):
            if unique and edit[0] < unique[-1][1]:
                continue
            unique.append(edit)

        for start, end, replacement in reversed(unique):
            content = content[:start] + replacement + content[end:]

        changes = [
            f"{_line(content, start)}: replaced overflow-guarded "
            f"Math.abs({variable}) with Math.absExact({variable}); "
            f"reason=Integer.MIN_VALUE must throw ArithmeticException"
            for start, end, replacement in unique
            for variable in [re.match(r"Math\.absExact\((.*)\)", replacement).group(1)]
        ]
        return content, changes
