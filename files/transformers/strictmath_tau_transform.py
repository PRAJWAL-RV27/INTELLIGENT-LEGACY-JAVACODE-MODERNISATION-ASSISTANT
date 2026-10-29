"""Replace exact ``2 * StrictMath.PI`` expressions with ``StrictMath.TAU``.

This rule is deliberately conservative.  The repository does not include a Java
parser, so it uses a same-length source mask and small, balanced-parentheses
checks instead of regular-expression replacement.  Masking keeps comments,
strings, and character/text literals in place while expression offsets remain
stable.
"""
from __future__ import annotations

import re


_IDENTIFIER = r"[A-Za-z_$][A-Za-z0-9_$]*"
# Java numeric literals equal to positive two.  Long/floating suffixes are
# harmless because the other operand is a double.
_TWO_LITERAL = re.compile(
    r"(?:2(?:\.0*)?|2(?:[Ee][+-]?\d+)?[dDfFlLsS]?|"
    r"0x2(?:\.0*)?[Pp][+-]?\d+[dDfF]?|"
    r"0x2(?:[uUlL]*)?)\Z"
)
_QUALIFIED_PI = re.compile(
    rf"StrictMath\s*\.\s*PI\b",
)
_STATIC_PI = re.compile(rf"\bPI\b")
_DECLARATION_SHADOWS = re.compile(
    rf"(?<![\w$.])(?:{_IDENTIFIER}\s+)?"
    rf"(StrictMath|PI)\s*(?:=|[,;)]|$)",
)


def _mask(source: str) -> str:
    """Return a same-length source mask containing only Java code tokens."""
    out: list[str] = []
    i = 0
    length = len(source)
    while i < length:
        char = source[i]
        following = source[i + 1] if i + 1 < length else ""

        if char == "/" and following == "/":
            end = source.find("\n", i)
            end = length if end == -1 else end
            out.append(" " * (end - i))
            i = end
        elif char == "/" and following == "*":
            end = source.find("*/", i + 2)
            end = length if end == -1 else end + 2
            out.append("".join("\n" if item == "\n" else " "
                                for item in source[i:end]))
            i = end
        elif source.startswith('"""', i):
            end = source.find('"""', i + 3)
            end = length if end == -1 else end + 3
            out.append('"""' + "".join("\n" if item == "\n" else " "
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
            out.append(char + "_" * max(0, end - i - 2)
                       + (source[end - 1] if end > i + 1 else ""))
            i = end
        else:
            out.append(char)
            i += 1
    return "".join(out)


def _skip(masked: str, index: int, step: int) -> int:
    while 0 <= index < len(masked) and masked[index].isspace():
        index += step
    return index


def _matching_parenthesis(masked: str, open_index: int) -> int:
    depth = 0
    i = open_index
    while i < len(masked):
        if masked[i] == "(":
            depth += 1
        elif masked[i] == ")":
            depth -= 1
            if depth == 0:
                return i
        i += 1
    return -1


def _opening_parenthesis(masked: str, close_index: int) -> int:
    depth = 0
    i = close_index
    while i >= 0:
        if masked[i] == ")":
            depth += 1
        elif masked[i] == "(":
            depth -= 1
            if depth == 0:
                return i
        i -= 1
    return -1


def _operand_before(masked: str, index: int) -> tuple[int, int] | None:
    end = _skip(masked, index - 1, -1) + 1
    if end <= 0:
        return None
    index = end - 1
    if masked[index] == ")":
        start = _opening_parenthesis(masked, index)
        if start < 0:
            return None
        return start, end
    start = index
    while start >= 0 and (masked[start].isalnum() or masked[start] in "_$."):
        start -= 1
    start += 1
    return (start, end) if start < end else None


def _operand_after(masked: str, index: int) -> tuple[int, int] | None:
    start = _skip(masked, index, 1)
    if start >= len(masked):
        return None
    if masked[start] == "(":
        end = _matching_parenthesis(masked, start)
        if end < 0:
            return None
        return start, end + 1
    end = start
    while end < len(masked) and (masked[end].isalnum() or masked[end] in "_$."):
        end += 1
    return (start, end) if start < end else None


def _unwrap(masked: str, start: int, end: int) -> tuple[int, int]:
    """Remove balanced outer parentheses, without changing source offsets."""
    while True:
        left = _skip(masked, start, 1)
        right = _skip(masked, end - 1, -1)
        if left >= end or masked[left] != "(" or masked[right] != ")":
            return start, end
        close = _matching_parenthesis(masked, left)
        if close != right:
            return start, end
        start, end = left + 1, close


def _is_two(masked: str, start: int, end: int) -> bool:
    start, end = _unwrap(masked, start, end)
    text = masked[start:end].strip()
    # Hex integer Java literals use no decimal point.  Decimal suffixes are
    # handled by the regex; underscores are normalized away.
    if text.startswith("0x") or text.startswith("0X"):
        text = text.replace("_", "")
    return bool(_TWO_LITERAL.fullmatch(text.replace("_", "")))


def _static_pi_origins(masked: str) -> set[str]:
    origins: set[str] = set()
    for match in re.finditer(
        r"\bimport\s+static\s+java\.lang\.StrictMath\.\s*(PI|\*)\s*;",
        masked,
    ):
        origins.add(match.group(1))
    return origins


def _pi_is_shadowed(masked: str, position: int) -> bool:
    prefix = masked[:position]
    if re.search(r"\b(?:PI|StrictMath)\b", prefix):
        for match in _DECLARATION_SHADOWS.finditer(prefix):
            if match.group(1):
                return True
    return False


def _valid_pi(masked: str, start: int, end: int,
              static_origins: set[str]) -> bool:
    token = masked[start:end]
    if token.startswith("StrictMath"):
        return not _pi_is_shadowed(masked, start)
    if "PI" not in static_origins and "*" not in static_origins:
        return False
    return not _pi_is_shadowed(masked, start)


def _extend_outer_parentheses(masked: str, start: int, end: int
                              ) -> tuple[int, int]:
    while True:
        left = _skip(masked, start - 1, -1)
        if left < 0 or masked[left] != "(":
            return start, end
        close = _matching_parenthesis(masked, left)
        if close != _skip(masked, end, 1):
            return start, end
        start, end = left, close + 1


def _comments_in(source: str, start: int, end: int) -> str:
    comments: list[str] = []
    index = start
    while index < end:
        if source.startswith("//", index):
            finish = source.find("\n", index)
            finish = end if finish == -1 else min(finish, end)
            comments.append(source[index:finish])
            index = finish
        elif source.startswith("/*", index):
            finish = source.find("*/", index + 2)
            finish = end if finish == -1 else min(finish + 2, end)
            comments.append(source[index:finish])
            index = finish
        else:
            index += 1
    return "".join(comment + ("\n" if comment.startswith("//") else "")
                   for comment in comments)


class StrictMathTauTransformer:
    """Java 19+ semantic-preserving TAU expression modernization."""

    NAME = "StrictMath.PI doubling -> StrictMath.TAU"
    requires_performance_evaluation = False

    def __init__(self, target_java_version: int = 21,
                 enabled: bool = True) -> None:
        self.target_java_version = target_java_version
        self.enabled = enabled

    def configure(self, target_java_version: int, enabled: bool = True) -> None:
        self.target_java_version = target_java_version
        self.enabled = enabled

    def transform(self, content: str) -> tuple[str, list[str]]:
        if not self.enabled or self.target_java_version < 19:
            return content, []

        masked = _mask(content)
        static_origins = _static_pi_origins(masked)
        edits: list[tuple[int, int, str, str]] = []

        # Existing edits are never recursively considered.  This makes the
        # operation idempotent while preserving source positions.
        for match in re.finditer(
            rf"(?:StrictMath\s*\.\s*PI\b|{_STATIC_PI.pattern})",
            masked,
        ):
            start, end = match.span()
            qualified = masked[start:end].startswith("StrictMath")
            if not qualified and start < len(masked):
                # A PI token is eligible only with a verified static import.
                pass
            if not _valid_pi(masked, start, end, static_origins):
                continue

            pi_start, pi_end = _extend_outer_parentheses(masked, start, end)

            # 2 * PI
            operator = _skip(masked, pi_start - 1, -1)
            before = (
                _operand_before(masked, operator)
                if operator >= 0 and masked[operator] == "*"
                else None
            )
            if before is not None:
                factor_start, factor_end = before
                if _is_two(masked, factor_start, factor_end):
                    factor_start, factor_end = _extend_outer_parentheses(
                        masked, factor_start, factor_end
                    )
                    edit_start, edit_end = factor_start, pi_end
                    comments = _comments_in(content, edit_start, edit_end)
                    replacement = (
                        comments + ("" if comments.endswith("\n") else " ")
                        + "StrictMath.TAU"
                        if comments else "StrictMath.TAU"
                    )
                    edits.append((edit_start, edit_end, replacement,
                                  f"Replaced 2 * StrictMath.PI at line "
                                  f"{content[:edit_start].count(chr(10)) + 1}"))
                    continue

            # PI * 2
            operator = _skip(masked, pi_end, 1)
            after = (
                _operand_after(masked, operator + 1)
                if operator >= 0 and masked[operator] == "*"
                else None
            )
            if after is not None:
                factor_start, factor_end = after
                if _is_two(masked, factor_start, factor_end):
                    factor_start, factor_end = _extend_outer_parentheses(
                        masked, factor_start, factor_end
                    )
                    edit_start, edit_end = pi_start, factor_end
                    comments = _comments_in(content, edit_start, edit_end)
                    replacement = (
                        comments + ("" if comments.endswith("\n") else " ")
                        + "StrictMath.TAU"
                        if comments else "StrictMath.TAU"
                    )
                    edits.append((edit_start, edit_end, replacement,
                                  f"Replaced StrictMath.PI * 2 at line "
                                  f"{content[:edit_start].count(chr(10)) + 1}"))

        # Sort from the right, and remove overlapping matches before editing.
        unique: list[tuple[int, int, str, str]] = []
        for edit in sorted(edits, key=lambda item: item[0]):
            if unique and edit[0] < unique[-1][1]:
                continue
            unique.append(edit)

        for start, end, replacement, _reason in reversed(unique):
            content = content[:start] + replacement + content[end:]

        changes = [
            f"{reason}; replacement=StrictMath.TAU; reason="
            f"semantically equivalent Java double constant expression"
            for _, _, _, reason in unique
        ]
        return content, changes
