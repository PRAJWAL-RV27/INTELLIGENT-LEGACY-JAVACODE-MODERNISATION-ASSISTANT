"""
toolkit_createcomponent_transform.py

Java 8 -> Java 21 migration.

Removes obsolete Toolkit.createComponent(Component)
overrides that return LightweightPeer.

The transformer:
- only targets classes extending Toolkit
- only removes the direct Toolkit method
- preserves unrelated methods and nested classes
- correctly handles nested braces
- ignores braces inside strings, character literals and comments
- removes LightweightPeer import ONLY when the peer type is no longer
  referenced anywhere else in the file
- adds no replacement code
- adds no manual-migration comments
"""

import re

from .base_transformer import BaseTransformer


class ToolkitCreateComponentTransformer(BaseTransformer):

    METHOD_NAME = "createComponent"
    COMPONENT_TYPE = "Component"
    PEER_TYPE = "LightweightPeer"

    @staticmethod
    def _matching_brace(content: str, open_index: int) -> int | None:
        depth = 0
        i = open_index

        quote = None
        escaped = False
        line_comment = False
        block_comment = False

        while i < len(content):
            char = content[i]
            next_char = content[i + 1] if i + 1 < len(content) else ""

            if line_comment:
                if char == "\n":
                    line_comment = False

            elif block_comment:
                if char == "*" and next_char == "/":
                    block_comment = False
                    i += 1

            elif quote is not None:
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == quote:
                    quote = None

            else:
                if char in ('"', "'"):
                    quote = char

                elif char == "/" and next_char == "/":
                    line_comment = True
                    i += 1

                elif char == "/" and next_char == "*":
                    block_comment = True
                    i += 1

                elif char == "{":
                    depth += 1

                elif char == "}":
                    depth -= 1

                    if depth == 0:
                        return i

            i += 1

        return None

    @staticmethod
    def _brace_depth(content: str, start: int, end: int) -> int:
        depth = 0
        i = start

        quote = None
        escaped = False
        line_comment = False
        block_comment = False

        while i < end:
            char = content[i]
            next_char = content[i + 1] if i + 1 < end else ""

            if line_comment:
                if char == "\n":
                    line_comment = False

            elif block_comment:
                if char == "*" and next_char == "/":
                    block_comment = False
                    i += 1

            elif quote is not None:
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == quote:
                    quote = None

            else:
                if char in ('"', "'"):
                    quote = char

                elif char == "/" and next_char == "/":
                    line_comment = True
                    i += 1

                elif char == "/" and next_char == "*":
                    block_comment = True
                    i += 1

                elif char == "{":
                    depth += 1

                elif char == "}":
                    depth -= 1

            i += 1

        return depth

    @classmethod
    def _toolkit_class_ranges(cls, content: str):
        pattern = re.compile(
            r"\bclass\s+[A-Za-z_$][\w$]*"
            r"(?:\s*<[^{}>]*>)?"
            r"\s+extends\s+(?:[\w$]+\.)*Toolkit\b"
            r"[^{]*\{"
        )

        ranges = []

        for match in pattern.finditer(content):
            close = cls._matching_brace(
                content,
                match.end() - 1,
            )

            if close is not None:
                ranges.append(
                    (match.end() - 1, close + 1)
                )

        return ranges

    @classmethod
    def _method_pattern(cls):
        return re.compile(
            rf"(?m)^[ \t]*"
            rf"(?:(?:@[^\n]*\n)[ \t]*)*"
            rf"(?:(?:public|protected|private|abstract|static|final|"
            rf"synchronized|native|strictfp)\s+)+"
            rf"(?P<return_type>"
            rf"[\w.$]+(?:\s*<[^;{{}}()]*>)?"
            rf")\s+"
            rf"{re.escape(cls.METHOD_NAME)}"
            rf"\s*\(\s*"
            rf"(?:final\s+)?"
            rf"(?:[\w.$]+\.)?"
            rf"{re.escape(cls.COMPONENT_TYPE)}"
            rf"\s+[A-Za-z_$][\w$]*"
            rf"\s*\)"
            rf"\s*"
            rf"(?:throws\s+[^\{{;]+)?"
            rf"\s*"
            rf"(?P<terminator>\{{|;)"
        )

    @classmethod
    def _remove_methods(cls, content: str):
        removals = []
        pattern = cls._method_pattern()

        for class_open, class_end in cls._toolkit_class_ranges(content):

            for match in pattern.finditer(
                content,
                class_open + 1,
                class_end,
            ):
                if cls._brace_depth(
                    content,
                    class_open + 1,
                    match.start(),
                ) != 0:
                    continue

                if cls.PEER_TYPE not in match.group("return_type"):
                    continue

                if match.group("terminator") == ";":
                    end = match.end()

                else:
                    close = cls._matching_brace(
                        content,
                        match.end() - 1,
                    )

                    if close is None:
                        continue

                    end = close + 1

                while end < len(content) and content[end] in " \t":
                    end += 1

                if content.startswith("\r\n", end):
                    end += 2
                elif end < len(content) and content[end] in "\r\n":
                    end += 1

                removals.append((match.start(), end))

        if not removals:
            return content, 0

        result = content

        for start, end in sorted(set(removals), reverse=True):
            result = result[:start] + result[end:]

        return result, len(set(removals))

    @classmethod
    def _remove_unused_peer_import(cls, content: str) -> str:
        """
        Remove LightweightPeer import only if LightweightPeer is no
        longer referenced anywhere else in the source.
        """

        import_pattern = re.compile(
            rf"(?m)^[ \t]*"
            rf"import\s+java\.awt\.peer\."
            rf"{re.escape(cls.PEER_TYPE)}\s*;"
            rf"[ \t]*(?:\r?\n)?"
        )

        without_import, count = import_pattern.subn(
            "",
            content,
        )

        if count == 0:
            return content

        if re.search(
            rf"\b{re.escape(cls.PEER_TYPE)}\b",
            without_import,
        ):
            return content

        return without_import

    def transform(self, content: str) -> tuple[str, list[str]]:
        result, count = self._remove_methods(content)

        if count == 0:
            return content, []

        result = self._remove_unused_peer_import(result)

        changes = [
            f"Removed {count}× obsolete "
            "`Toolkit.createComponent(Component)` override"
        ]

        return result, changes