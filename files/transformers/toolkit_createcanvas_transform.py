"""
toolkit_createcanvas_transform.py

Java 8 -> Java 21 migration.

Removes the obsolete Toolkit.createCanvas(Canvas) override.
"""

import re

from .base_transformer import BaseTransformer


class ToolkitCreateCanvasTransformer(BaseTransformer):

    METHOD_NAME = "createCanvas"
    COMPONENT_TYPE = "Canvas"
    PEER_TYPE = "CanvasPeer"

    @staticmethod
    def _find_matching_brace(content: str, open_index: int) -> int | None:
        depth = 0
        i = open_index

        in_string = None
        escaped = False
        in_line_comment = False
        in_block_comment = False

        while i < len(content):
            char = content[i]
            next_char = content[i + 1] if i + 1 < len(content) else ""

            if in_line_comment:
                if char == "\n":
                    in_line_comment = False

            elif in_block_comment:
                if char == "*" and next_char == "/":
                    in_block_comment = False
                    i += 1

            elif in_string:
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == in_string:
                    in_string = None

            else:
                if char in ('"', "'"):
                    in_string = char
                elif char == "/" and next_char == "/":
                    in_line_comment = True
                    i += 1
                elif char == "/" and next_char == "*":
                    in_block_comment = True
                    i += 1
                elif char == "{":
                    depth += 1
                elif char == "}":
                    depth -= 1

                    if depth == 0:
                        return i

            i += 1

        return None

    @classmethod
    def _toolkit_class_ranges(cls, content: str) -> list[tuple[int, int]]:
        pattern = re.compile(
            r"\bclass\s+\w+"
            r"(?:\s*<[^{}>]+>)?"
            r"\s+extends\s+(?:[\w$]+\.)*Toolkit\b"
            r"[^{]*\{"
        )

        ranges = []

        for match in pattern.finditer(content):
            close = cls._find_matching_brace(
                content,
                match.end() - 1,
            )

            if close is not None:
                ranges.append((match.start(), close + 1))

        return ranges

    @classmethod
    def _remove_method(cls, content: str) -> tuple[str, int]:
        method_pattern = re.compile(
            rf"(?m)^"
            rf"(?P<indent>[ \t]*)"
            rf"(?P<annotations>"
            rf"(?:(?:@[^\n]*\n)[ \t]*)*"
            rf")"
            rf"(?P<modifiers>"
            rf"(?:(?:public|protected|private|abstract|static|final|"
            rf"synchronized|native|strictfp)\s+)*"
            rf")"
            rf"(?P<return_type>"
            rf"[\w.$]+"
            rf"(?:\s*<[^;{{}}()]*>)?"
            rf"\s+"
            rf")"
            rf"{re.escape(cls.METHOD_NAME)}"
            rf"\s*\(\s*"
            rf"(?:final\s+)?"
            rf"(?:[\w.$]+\.)?"
            rf"{re.escape(cls.COMPONENT_TYPE)}"
            rf"\s+\w+"
            rf"\s*\)"
            rf"\s*"
            rf"(?:throws\s+[^\{{;]+)?"
            rf"\s*"
            rf"(?P<terminator>\{{|;)"
        )

        toolkit_ranges = cls._toolkit_class_ranges(content)
        removals = []

        for match in method_pattern.finditer(content):

            if cls.PEER_TYPE not in match.group("return_type"):
                continue

            if not any(
                start <= match.start() < end
                for start, end in toolkit_ranges
            ):
                continue

            if match.group("terminator") == ";":
                end = match.end()
            else:
                close = cls._find_matching_brace(
                    content,
                    match.end() - 1,
                )

                if close is None:
                    continue

                end = close + 1

            while end < len(content) and content[end] in " \t":
                end += 1

            if end < len(content) and content[end] == "\n":
                end += 1

            removals.append((match.start(), end))

        result = content

        for start, end in reversed(removals):
            result = result[:start] + result[end:]

        return result, len(removals)

    @classmethod
    def _remove_unused_peer_import(cls, content: str) -> str:
        if re.search(rf"\b{re.escape(cls.PEER_TYPE)}\b", content):
            return content

        content = re.sub(
            r"(?m)^[ \t]*import\s+java\.awt\.peer\.CanvasPeer\s*;\s*\n?",
            "",
            content,
        )

        peer_type_names = (
            r"ButtonPeer|CanvasPeer|CheckboxPeer|CheckboxMenuItemPeer|"
            r"ChoicePeer|ComponentPeer|DialogPeer|FileDialogPeer|"
            r"FramePeer|LabelPeer|ListPeer|MenuPeer|MenuItemPeer|"
            r"PanelPeer|PopupMenuPeer|ScrollbarPeer|ScrollPanePeer|"
            r"TextAreaPeer|TextFieldPeer|TextComponentPeer|WindowPeer"
        )

        if not re.search(rf"\b(?:{peer_type_names})\b", content):
            content = re.sub(
                r"(?m)^[ \t]*import\s+java\.awt\.peer\.\*\s*;\s*\n?",
                "",
                content,
            )

        return content

    def transform(self, content: str) -> tuple[str, list[str]]:
        result, count = self._remove_method(content)

        if count == 0:
            return content, []

        result = self._remove_unused_peer_import(result)

        changes = [
            f"Removed {count}× obsolete "
            "`Toolkit.createCanvas(Canvas)` override"
        ]

        return result, changes