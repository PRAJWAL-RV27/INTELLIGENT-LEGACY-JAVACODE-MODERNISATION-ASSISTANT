import re

from .base_transformer import BaseTransformer


class FinalizeTransformer(BaseTransformer):
    """
    Safely handles legacy finalize() methods.

    Rules:

    1. Empty finalize() methods are removed.
    2. finalize() methods containing only super.finalize() are removed.
    3. finalize() methods containing real subclass cleanup logic are left
       unchanged because replacing finalize() with close() changes lifecycle
       semantics.
    4. No manual-review markers are generated.
    5. No AutoCloseable implementation is added automatically.
    6. No helper methods or helper classes are generated.

    The transformer is deliberately conservative because there is no
    universally semantics-preserving replacement for arbitrary finalizers.
    """

    _FINALIZE_HEADER = re.compile(
        r"""
        (?P<annotations>
            (?:
                @
                [A-Za-z_$][\w$]*
                (?:\s*\([^)]*\))?
                \s*
            )*
        )
        (?P<visibility>
            public|protected
        )
        \s+
        void
        \s+
        finalize
        \s*
        \(
        \s*
        \)
        \s*
        (?:
            throws
            \s+
            [^{]+
        )?
        \s*
        \{
        """,
        re.VERBOSE | re.DOTALL,
    )

    def transform(self, content: str):

        changes = []

        search_from = 0

        while True:

            match = self._find_next_finalize(
                content,
                search_from,
            )

            if match is None:
                break

            brace_start = match.end() - 1

            method_end = self._find_matching_brace(
                content,
                brace_start,
            )

            # ----------------------------------------------------------
            # Never modify malformed Java source.
            # ----------------------------------------------------------

            if method_end is None:
                break

            method_body = content[
                brace_start + 1:
                method_end
            ]

            # ----------------------------------------------------------
            # CASE 1:
            #
            # Empty finalize()
            #
            # This is safe to remove because it contributes no behavior.
            # ----------------------------------------------------------

            if self._is_empty_body(method_body):

                method_start = match.start()

                content = (
                    content[:method_start]
                    + content[method_end + 1:]
                )

                changes.append(
                    "Removed empty finalize() method."
                )

                # Content before the removed method is unchanged.
                search_from = method_start
                continue

            # ----------------------------------------------------------
            # CASE 2:
            #
            # finalize() containing only:
            #
            #     super.finalize();
            #
            # This override adds no subclass behavior.
            # ----------------------------------------------------------

            if self._is_only_super_finalize(method_body):

                method_start = match.start()

                content = (
                    content[:method_start]
                    + content[method_end + 1:]
                )

                changes.append(
                    "Removed redundant finalize() override."
                )

                search_from = method_start
                continue

            # ----------------------------------------------------------
            # CASE 3:
            #
            # Real cleanup logic.
            #
            # DO NOT convert to close().
            #
            # close() is not automatically invoked when the object becomes
            # unreachable, so doing:
            #
            #     finalize() -> close()
            #
            # would change program behavior.
            #
            # Leave the original method untouched.
            # ----------------------------------------------------------

            search_from = method_end + 1

        return content, changes

    # ==================================================================
    # FINALIZE DISCOVERY
    # ==================================================================

    def _find_next_finalize(
        self,
        content: str,
        start: int,
    ):
        """
        Find the next real finalize() declaration.

        Occurrences inside strings and comments are ignored.
        """

        for match in self._FINALIZE_HEADER.finditer(
            content,
            start,
        ):

            if not self._inside_ignored_region(
                content,
                match.start(),
            ):
                return match

        return None

    # ==================================================================
    # BODY CLASSIFICATION
    # ==================================================================

    def _is_empty_body(
        self,
        body: str,
    ) -> bool:

        cleaned = self._remove_comments(
            body
        )

        return not cleaned.strip()

    def _is_only_super_finalize(
        self,
        body: str,
    ) -> bool:

        cleaned = self._remove_comments(
            body
        )

        # Normalize whitespace only.
        #
        # Do not remove arbitrary characters because doing so could make
        # different Java statements appear equivalent.
        normalized = re.sub(
            r"\s+",
            "",
            cleaned,
        )

        return normalized == "super.finalize();"

    # ==================================================================
    # COMMENT HANDLING
    # ==================================================================

    def _remove_comments(
        self,
        text: str,
    ) -> str:
        """
        Remove Java comments while preserving string and character literals.

        This is used only for determining whether a body is empty or consists
        solely of super.finalize().
        """

        result = []

        i = 0
        n = len(text)

        while i < n:

            # ----------------------------------------------------------
            # Java text block
            # ----------------------------------------------------------

            if text.startswith('"""', i):

                start = i
                i += 3

                while i < n:

                    if text.startswith('"""', i):
                        i += 3
                        break

                    if text[i] == "\\":
                        i += 2
                    else:
                        i += 1

                result.append(
                    text[start:i]
                )

                continue

            # ----------------------------------------------------------
            # String literal
            # ----------------------------------------------------------

            if text[i] == '"':

                start = i
                i += 1

                while i < n:

                    if text[i] == "\\":
                        i += 2
                        continue

                    if text[i] == '"':
                        i += 1
                        break

                    i += 1

                result.append(
                    text[start:i]
                )

                continue

            # ----------------------------------------------------------
            # Character literal
            # ----------------------------------------------------------

            if text[i] == "'":

                start = i
                i += 1

                while i < n:

                    if text[i] == "\\":
                        i += 2
                        continue

                    if text[i] == "'":
                        i += 1
                        break

                    i += 1

                result.append(
                    text[start:i]
                )

                continue

            # ----------------------------------------------------------
            # Line comment
            # ----------------------------------------------------------

            if (
                text[i] == "/"
                and i + 1 < n
                and text[i + 1] == "/"
            ):

                newline = text.find(
                    "\n",
                    i + 2,
                )

                if newline == -1:
                    break

                i = newline
                continue

            # ----------------------------------------------------------
            # Block comment
            # ----------------------------------------------------------

            if (
                text[i] == "/"
                and i + 1 < n
                and text[i + 1] == "*"
            ):

                end = text.find(
                    "*/",
                    i + 2,
                )

                if end == -1:
                    # Malformed comment. Return the original text so that
                    # the caller will not incorrectly classify the body.
                    return text

                i = end + 2
                continue

            result.append(
                text[i]
            )

            i += 1

        return "".join(result)

    # ==================================================================
    # BRACE MATCHING
    # ==================================================================

    def _find_matching_brace(
        self,
        content: str,
        opening_brace: int,
    ):
        """
        Find the closing brace corresponding to opening_brace.

        Braces inside strings, characters, text blocks, and comments are
        ignored.
        """

        depth = 0
        i = opening_brace
        n = len(content)

        while i < n:

            # ----------------------------------------------------------
            # Text block
            # ----------------------------------------------------------

            if content.startswith('"""', i):

                i += 3

                while i < n:

                    if content.startswith('"""', i):
                        i += 3
                        break

                    if content[i] == "\\":
                        i += 2
                    else:
                        i += 1

                continue

            # ----------------------------------------------------------
            # String
            # ----------------------------------------------------------

            if content[i] == '"':

                i += 1

                while i < n:

                    if content[i] == "\\":
                        i += 2
                        continue

                    if content[i] == '"':
                        i += 1
                        break

                    i += 1

                continue

            # ----------------------------------------------------------
            # Character
            # ----------------------------------------------------------

            if content[i] == "'":

                i += 1

                while i < n:

                    if content[i] == "\\":
                        i += 2
                        continue

                    if content[i] == "'":
                        i += 1
                        break

                    i += 1

                continue

            # ----------------------------------------------------------
            # Line comment
            # ----------------------------------------------------------

            if (
                content[i] == "/"
                and i + 1 < n
                and content[i + 1] == "/"
            ):

                newline = content.find(
                    "\n",
                    i + 2,
                )

                if newline == -1:
                    return None

                i = newline + 1
                continue

            # ----------------------------------------------------------
            # Block comment
            # ----------------------------------------------------------

            if (
                content[i] == "/"
                and i + 1 < n
                and content[i + 1] == "*"
            ):

                end = content.find(
                    "*/",
                    i + 2,
                )

                if end == -1:
                    return None

                i = end + 2
                continue

            # ----------------------------------------------------------
            # Braces
            # ----------------------------------------------------------

            if content[i] == "{":

                depth += 1

            elif content[i] == "}":

                depth -= 1

                if depth == 0:
                    return i

            i += 1

        return None

    # ==================================================================
    # STRING / COMMENT SAFETY
    # ==================================================================

    def _inside_ignored_region(
        self,
        content: str,
        position: int,
    ) -> bool:
        """
        Return True when position lies inside a string, character literal,
        text block, or comment.
        """

        i = 0
        n = min(
            position,
            len(content),
        )

        while i < n:

            # ----------------------------------------------------------
            # Text block
            # ----------------------------------------------------------

            if content.startswith('"""', i):

                i += 3

                while i < n:

                    if content.startswith('"""', i):
                        i += 3
                        break

                    if content[i] == "\\":
                        i += 2
                    else:
                        i += 1

                continue

            # ----------------------------------------------------------
            # String
            # ----------------------------------------------------------

            if content[i] == '"':

                i += 1

                while i < n:

                    if content[i] == "\\":
                        i += 2
                        continue

                    if content[i] == '"':
                        i += 1
                        break

                    i += 1

                continue

            # ----------------------------------------------------------
            # Character
            # ----------------------------------------------------------

            if content[i] == "'":

                i += 1

                while i < n:

                    if content[i] == "\\":
                        i += 2
                        continue

                    if content[i] == "'":
                        i += 1
                        break

                    i += 1

                continue

            # ----------------------------------------------------------
            # Line comment
            # ----------------------------------------------------------

            if (
                content[i] == "/"
                and i + 1 < n
                and content[i + 1] == "/"
            ):

                newline = content.find(
                    "\n",
                    i + 2,
                )

                if newline == -1:
                    return True

                i = newline + 1
                continue

            # ----------------------------------------------------------
            # Block comment
            # ----------------------------------------------------------

            if (
                content[i] == "/"
                and i + 1 < n
                and content[i + 1] == "*"
            ):

                end = content.find(
                    "*/",
                    i + 2,
                )

                if end == -1:
                    return True

                if position <= end + 2:
                    return True

                i = end + 2
                continue

            i += 1

        return False