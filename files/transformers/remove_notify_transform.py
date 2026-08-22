import re

from .base_transformer import BaseTransformer


class RemoveNotifyTransformer(BaseTransformer):
    """
    Safely removes redundant removeNotify() overrides.

    removeNotify() is NOT removed from Java 21. It is still part of the
    AWT/Swing component lifecycle and is called by the toolkit.

    Therefore:

        protected void removeNotify() {
            super.removeNotify();
        }

    can safely be removed because the inherited implementation performs
    exactly the same operation.

    However, a removeNotify() containing any additional logic must be left
    untouched. Renaming it to another method would change lifecycle semantics
    because the new method would not be called automatically by AWT.

    This transformer:
      - never creates a replacement method
      - never creates manual-review markers
      - never removes custom cleanup logic
      - never changes method semantics
      - handles nested braces safely
      - ignores braces inside strings/comments
    """

    _METHOD_HEADER = re.compile(
        r"""
        (?P<annotations>
            (?:(?:@\s*[A-Za-z_$][\w$]*(?:\s*\([^)]*\))?)
            \s*)*
        )
        (?P<visibility>
            public|protected
        )
        \s+
        void
        \s+
        removeNotify
        \s*
        \(
        \s*
        \)
        \s*
        (?P<throws>
            throws\s+[^{]+
        )?
        \{
        """,
        re.VERBOSE | re.DOTALL,
    )

    def transform(self, content: str):

        changes = []

        while True:

            match = self._find_remove_notify(content)

            if match is None:
                break

            brace_start = match.end() - 1

            method_end = self._find_matching_brace(
                content,
                brace_start,
            )

            # Never modify malformed/unbalanced Java.
            if method_end is None:
                break

            body = content[
                brace_start + 1:
                method_end
            ]

            # ----------------------------------------------------------
            # Only remove a method whose effective body is exactly:
            #
            #     super.removeNotify();
            #
            # Whitespace and comments are allowed.
            #
            # Anything else is preserved completely.
            # ----------------------------------------------------------

            if not self._is_redundant_super_call(body):
                # Find the next removeNotify(), rather than repeatedly
                # examining the same method.
                next_start = method_end + 1

                next_match = self._find_remove_notify(
                    content,
                    next_start,
                )

                if next_match is None:
                    break

                # Process the later occurrence.
                content = (
                    content[:next_start]
                    + content[next_start:]
                )

                # Avoid infinite looping by temporarily replacing the
                # current method with itself and searching from its end.
                # Since the content is unchanged, use a direct search.
                later = self._find_next_redundant_method(
                    content,
                    next_start,
                )

                if later is None:
                    break

                match = later
                brace_start = match.end() - 1
                method_end = self._find_matching_brace(
                    content,
                    brace_start,
                )

                if method_end is None:
                    break

                body = content[
                    brace_start + 1:
                    method_end
                ]

                if not self._is_redundant_super_call(body):
                    break

            # ----------------------------------------------------------
            # Remove only the redundant override.
            #
            # The inherited removeNotify() remains available, so the
            # component lifecycle behavior is preserved.
            # ----------------------------------------------------------

            method_start = match.start()

            content = (
                content[:method_start]
                + content[method_end + 1:]
            )

            changes.append(
                "Removed redundant removeNotify() override; "
                "inherited implementation is preserved."
            )

        return content, changes

    # ------------------------------------------------------------------
    # Method discovery
    # ------------------------------------------------------------------

    def _find_remove_notify(
        self,
        content: str,
        start: int = 0,
    ):
        """
        Find a syntactically plausible removeNotify() declaration.

        The regex itself is intentionally conservative.  Before using the
        result, the body is validated with balanced-brace parsing.
        """

        for match in self._METHOD_HEADER.finditer(
            content,
            start,
        ):
            if not self._inside_comment_or_string(
                content,
                match.start(),
            ):
                return match

        return None

    def _find_next_redundant_method(
        self,
        content: str,
        start: int,
    ):
        """
        Locate the next removeNotify() declaration after start.
        """

        return self._find_remove_notify(
            content,
            start,
        )

    # ------------------------------------------------------------------
    # Redundant-body detection
    # ------------------------------------------------------------------

    def _is_redundant_super_call(
        self,
        body: str,
    ) -> bool:
        """
        Return True only when the method body contains exactly one
        super.removeNotify(); statement, ignoring comments/whitespace.

        Examples accepted:

            super.removeNotify();

            // comment
            super.removeNotify();

            /*
             * comment
             */
            super.removeNotify();

        Examples rejected:

            cleanup();
            super.removeNotify();

            super.removeNotify();
            cleanup();

            if (x)
                super.removeNotify();

            try {
                super.removeNotify();
            } finally {
                cleanup();
            }
        """

        cleaned = self._remove_comments(body)

        cleaned = re.sub(
            r"\s+",
            "",
            cleaned,
        )

        return cleaned == "super.removeNotify();"

    # ------------------------------------------------------------------
    # Comment removal
    # ------------------------------------------------------------------

    def _remove_comments(
        self,
        text: str,
    ) -> str:
        """
        Remove comments without treating comment text as Java statements.

        Strings and character literals are preserved.
        """

        result = []

        i = 0
        n = len(text)

        while i < n:

            # String literal
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

            # Character literal
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

            # Line comment
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

            # Block comment
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
                    # Malformed comment: do not pretend that the source
                    # is safely transformable.
                    return text

                i = end + 2
                continue

            result.append(text[i])
            i += 1

        return "".join(result)

    # ------------------------------------------------------------------
    # Balanced braces
    # ------------------------------------------------------------------

    def _find_matching_brace(
        self,
        content: str,
        opening_brace: int,
    ):
        """
        Find the closing brace corresponding to opening_brace.

        Braces inside:
          - strings
          - character literals
          - line comments
          - block comments

        are ignored.
        """

        depth = 0
        i = opening_brace
        n = len(content)

        while i < n:

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

    # ------------------------------------------------------------------
    # Defensive lexical check
    # ------------------------------------------------------------------

    def _inside_comment_or_string(
        self,
        content: str,
        position: int,
    ) -> bool:
        """
        Determine whether position is inside a string/comment.

        This prevents the method regex from matching text such as:

            // public void removeNotify() {
        """

        i = 0
        n = min(position, len(content))

        while i < n:

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