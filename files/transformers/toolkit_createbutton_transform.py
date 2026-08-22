"""
toolkit_createbutton_transform.py

Java 8 -> Java 21 migration.

Removes the obsolete Toolkit.createButton(Button) override.

Java 21 removed Toolkit.createButton(Button), which returned the
internal java.awt.peer.ButtonPeer type.

Transformation:

    @Override
    protected ButtonPeer createButton(Button target) {
        ...
    }

becomes:

    [method removed]

The transformer:
- only targets a createButton(Button) method inside a class extending Toolkit
- supports qualified types such as java.awt.peer.ButtonPeer
- supports concrete and abstract method declarations
- correctly handles nested braces, strings, character literals, and comments
- removes @Override annotations belonging to the removed method
- does not insert replacement code
- does not generate manual migration markers
"""

import re

from .base_transformer import BaseTransformer


class ToolkitCreateButtonTransformer(BaseTransformer):

    METHOD_NAME = "createButton"
    COMPONENT_TYPE = "Button"
    PEER_TYPE = "ButtonPeer"

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
        """
        Find classes that directly extend java.awt.Toolkit or Toolkit.
        """
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
        """
        Remove createButton(Button) declarations/implementations from
        direct Toolkit subclasses.
        """

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

            return_type = match.group("return_type")

            # Make sure this really is the ButtonPeer-returning API.
            if cls.PEER_TYPE not in return_type:
                continue

            # Do not touch methods outside a Toolkit subclass.
            inside_toolkit = any(
                start <= match.start() < end
                for start, end in toolkit_ranges
            )

            if not inside_toolkit:
                continue

            terminator = match.group("terminator")

            if terminator == ";":
                end = match.end()

            else:
                close = cls._find_matching_brace(
                    content,
                    match.end() - 1,
                )

                if close is None:
                    # Never modify malformed/incomplete source.
                    continue

                end = close + 1

            # Consume trailing horizontal whitespace.
            while end < len(content) and content[end] in " \t":
                end += 1

            # Consume one newline so we do not leave blank lines behind.
            if end < len(content) and content[end] == "\n":
                end += 1

            removals.append((match.start(), end))

        result = content

        for start, end in reversed(removals):
            result = result[:start] + result[end:]

        return result, len(removals)

    @classmethod
    def _remove_unused_peer_import(cls, content: str) -> str:
        """
        Remove an explicit ButtonPeer import only when no ButtonPeer
        type remains in the source.

        Wildcard java.awt.peer imports are removed only when no peer
        type usage remains at all.
        """

        if re.search(rf"\b{re.escape(cls.PEER_TYPE)}\b", content):
            return content

        content = re.sub(
            r"(?m)^[ \t]*import\s+java\.awt\.peer\.ButtonPeer\s*;\s*\n?",
            "",
            content,
        )

        # If there is no remaining java.awt.peer type usage, a wildcard
        # peer import is also unnecessary.
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
            "`Toolkit.createButton(Button)` override"
        ]

        return result, changes