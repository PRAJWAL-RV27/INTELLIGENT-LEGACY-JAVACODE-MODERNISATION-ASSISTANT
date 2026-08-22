"""
toolkit_createcanvas_transform.py

Java 8 -> Java 21 migration.

Removes obsolete Toolkit.createCanvas(Canvas) overrides
that return CanvasPeer.

The java.awt.peer package is not exported by Java 21.

The transformer removes only the obsolete override and its
directly attached Javadoc/annotations. Remaining CanvasPeer
references are reported rather than automatically rewritten.
"""

import re

from .base_transformer import BaseTransformer


class ToolkitCreateCanvasTransformer(BaseTransformer):

    METHOD_NAME = "createCanvas"
    COMPONENT_TYPE = "Canvas"
    PEER_TYPE = "CanvasPeer"

    @staticmethod
    def _matching_brace(content: str, open_index: int):
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
    def _brace_depth(content: str, start: int, end: int):
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
    def _class_ranges(cls, content: str):
        pattern = re.compile(
            r"\bclass\s+[A-Za-z_$][\w$]*"
            r"(?:\s*<[^{}>]*>)?\s*"
            r"(?:extends\s+(?P<super>[\w$.]+))?"
            r"(?:\s+implements\s+[^{]+)?\s*\{"
        )

        ranges = []

        for match in pattern.finditer(content):
            close = cls._matching_brace(
                content,
                match.end() - 1,
            )

            if close is None:
                continue

            superclass = match.group("super")

            if superclass:
                simple_name = superclass.rsplit(".", 1)[-1]

                if (
                    simple_name == "Toolkit"
                    or simple_name.endswith("Toolkit")
                ):
                    ranges.append(
                        (
                            match.end() - 1,
                            close + 1,
                        )
                    )

        return ranges

    @classmethod
    def _method_pattern(cls):
        return re.compile(
            rf"(?m)^[ \t]*"
            rf"(?:(?:public|protected|private|abstract|static|final|"
            rf"synchronized|native|strictfp)\s+)+"
            rf"(?P<return_type>"
            rf"[\w$.]+(?:\s*<[^;{{}}()]*>)?"
            rf")\s+"
            rf"{re.escape(cls.METHOD_NAME)}"
            rf"\s*\(\s*"
            rf"(?:final\s+)?"
            rf"(?:@[A-Za-z_$][\w$]*"
            rf"(?:\s*\([^;{{}}]*\))?\s+)*"
            rf"(?:[\w$.]+\s+)?"
            rf"[A-Za-z_$][\w$]*\s*\)"
            rf"\s*(?:throws\s+[^{{;]+)?\s*"
            rf"(?P<terminator>\{{|;)"
        )

    @staticmethod
    def _declaration_start(content: str, method_start: int) -> int:
        pos = method_start

        while True:
            while pos > 0 and content[pos - 1] in " \t\r\n":
                pos -= 1

            javadoc = re.search(
                r"/\*\*[\s\S]*?\*/[ \t]*(?:\r?\n[ \t]*)?$",
                content[:pos],
            )

            if javadoc:
                pos = javadoc.start()
                continue

            end = pos

            if end == 0:
                break

            if content[end - 1] == ")":
                depth = 0
                i = end - 1
                quote = None
                escaped = False

                while i >= 0:
                    char = content[i]

                    if quote is not None:
                        if escaped:
                            escaped = False
                        elif char == "\\":
                            escaped = True
                        elif char == quote:
                            quote = None
                    else:
                        if char in ('"', "'"):
                            quote = char
                        elif char == ")":
                            depth += 1
                        elif char == "(":
                            depth -= 1
                            if depth == 0:
                                break

                    i -= 1

                if i >= 0:
                    annotation_start = content.rfind("@", 0, i)

                    if annotation_start >= 0:
                        between = content[annotation_start:i]

                        if not re.search(r"[;{}]", between):
                            pos = annotation_start
                            continue

            line_start = content.rfind(
                "\n",
                0,
                end,
            ) + 1

            line = content[line_start:end].strip()

            if line.startswith("@"):
                pos = line_start
                continue

            break

        return pos

    @classmethod
    def _remove_methods(cls, content: str):
        removals = []
        pattern = cls._method_pattern()

        for class_open, class_end in cls._class_ranges(content):

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

                return_type = match.group(
                    "return_type"
                ).strip()

                if not re.fullmatch(
                    rf"(?:[\w$.]+\.)?"
                    rf"{re.escape(cls.PEER_TYPE)}",
                    return_type,
                ):
                    continue

                end = match.end()

                if match.group("terminator") == "{":
                    close = cls._matching_brace(
                        content,
                        end - 1,
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

                start = cls._declaration_start(
                    content,
                    match.start(),
                )

                removals.append((start, end))

        if not removals:
            return content, 0

        result = content

        for start, end in sorted(
            set(removals),
            reverse=True,
        ):
            result = result[:start] + result[end:]

        return result, len(set(removals))

    @classmethod
    def _remove_unused_peer_import(cls, content: str):
        import_pattern = re.compile(
            rf"(?m)^[ \t]*"
            rf"import\s+java\.awt\.peer\."
            rf"{re.escape(cls.PEER_TYPE)}"
            rf"\s*;[ \t]*(?:\r?\n)?"
        )

        without_import, count = import_pattern.subn(
            "",
            content,
        )

        if count == 0:
            return content, False

        if re.search(
            rf"\b{re.escape(cls.PEER_TYPE)}\b",
            without_import,
        ):
            return content, True

        return without_import, False

    def transform(
        self,
        content: str,
    ) -> tuple[str, list[str]]:

        result, count = self._remove_methods(content)

        if count == 0:
            return content, []

        result, remaining_peer_reference = (
            self._remove_unused_peer_import(result)
        )

        changes = [
            f"Removed {count}× obsolete "
            "`Toolkit.createCanvas(Canvas)` override"
        ]

        if remaining_peer_reference:
            changes.append(
                "`CanvasPeer` is still referenced elsewhere "
                "in the file; `java.awt.peer` is not exported "
                "by Java 21"
            )

        return result, changes