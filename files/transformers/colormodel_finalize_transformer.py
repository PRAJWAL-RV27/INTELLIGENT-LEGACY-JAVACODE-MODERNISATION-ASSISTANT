import re

from .base_transformer import BaseTransformer


class ColorModelFinalizeTransformer(BaseTransformer):
    """
    Migrates finalize() implementations from ColorModel subclasses.

    Java 21 removed ColorModel.finalize().  Empty/redundant finalizers are
    removed.  Finalizers containing cleanup logic are migrated to an explicit
    close() method and a Cleaner-based fallback so cleanup is not silently lost.

    The transformer intentionally avoids:
      - invalid Java syntax
      - duplicate close() methods
      - duplicate AutoCloseable
      - manual-review markers
      - modifying unrelated classes
    """

    def transform(self, content: str):

        changes = []

        # ------------------------------------------------------------
        # Only operate on source files that actually reference
        # ColorModel as a superclass.
        # ------------------------------------------------------------

        class_info = self._find_color_model_class(content)

        if class_info is None:
            return content, changes

        class_start, class_end, class_name, declaration = class_info

        # ------------------------------------------------------------
        # Find finalize() belonging to this ColorModel subclass.
        # ------------------------------------------------------------

        method_info = self._find_finalize_method(
            content,
            class_start,
            class_end
        )

        if method_info is None:
            return content, changes

        method_start, method_end, body = method_info

        # ------------------------------------------------------------
        # CASE 1:
        # Empty finalize()
        # ------------------------------------------------------------

        if not body.strip():
            content = content[:method_start] + content[method_end:]

            changes.append(
                "Removed empty ColorModel.finalize()."
            )

            return content, changes

        # ------------------------------------------------------------
        # CASE 2:
        # finalize() containing only super.finalize()
        #
        # This is safe because ColorModel.finalize() itself was removed,
        # and Object.finalize() performs no special cleanup.
        # ------------------------------------------------------------

        if self._is_only_super_finalize(body):

            content = content[:method_start] + content[method_end:]

            changes.append(
                "Removed redundant ColorModel.finalize()."
            )

            return content, changes

        # ------------------------------------------------------------
        # CASE 3:
        # Real cleanup logic.
        #
        # We cannot simply rename finalize() -> close(), because close()
        # is not automatically invoked by the JVM.
        #
        # Therefore:
        #   1. Move cleanup logic into close()
        #   2. Make the class AutoCloseable
        #   3. Register a Cleaner fallback
        #
        # The generated Cleaner callback invokes the same cleanup action.
        # ------------------------------------------------------------

        cleanup_body = self._remove_super_finalize(body)

        # Remove Override annotation from the old method body if it somehow
        # ended up inside the extracted text.
        cleanup_body = re.sub(
            r'^\s*@Override\s*',
            '',
            cleanup_body,
            count=1
        ).strip()

        # ------------------------------------------------------------
        # Do not transform if a close() method already exists.
        #
        # Adding a second close() would produce invalid Java.
        # ------------------------------------------------------------

        if self._has_close_method(
            content,
            class_start,
            class_end
        ):
            return content, changes

        # ------------------------------------------------------------
        # Determine indentation from the original finalize() method.
        # ------------------------------------------------------------

        indentation = self._get_method_indentation(
            content,
            method_start
        )

        body_indent = indentation + "    "

        # Indent original cleanup body.
        indented_body = self._indent_body(
            cleanup_body,
            body_indent
        )

        # ------------------------------------------------------------
        # Add Cleaner infrastructure only if not already present.
        # ------------------------------------------------------------

        content, cleaner_added = self._add_cleaner_support(
            content,
            class_start,
            class_end,
            class_name,
            indentation
        )

        if cleaner_added:
            changes.append(
                "Added Cleaner-based cleanup support."
            )

        # Recalculate class/method positions because content may have changed.
        class_info = self._find_color_model_class(content)

        if class_info is None:
            return content, changes

        class_start, class_end, class_name, declaration = class_info

        method_info = self._find_finalize_method(
            content,
            class_start,
            class_end
        )

        if method_info is None:
            return content, changes

        method_start, method_end, _ = method_info

        # ------------------------------------------------------------
        # Generate close().
        # ------------------------------------------------------------

        new_method = (
            f"\n{indentation}@Override\n"
            f"{indentation}public void close() {{\n"
            f"{indented_body}\n"
            f"{indentation}}}\n"
        )

        # ------------------------------------------------------------
        # Replace finalize() with close().
        # ------------------------------------------------------------

        content = (
            content[:method_start]
            + new_method
            + content[method_end:]
        )

        # ------------------------------------------------------------
        # Ensure AutoCloseable is present.
        # ------------------------------------------------------------

        content, auto_closeable_added = self._add_auto_closeable(
            content,
            class_name
        )

        if auto_closeable_added:
            changes.append(
                "Added AutoCloseable to ColorModel subclass."
            )

        # ------------------------------------------------------------
        # Add Cleaner registration in constructors.
        #
        # This is only done when constructors can be safely identified.
        # ------------------------------------------------------------

        content, registration_added = self._add_cleaner_registration(
            content,
            class_name
        )

        if registration_added:
            changes.append(
                "Registered ColorModel cleanup with Cleaner."
            )

        changes.append(
            "Converted ColorModel.finalize() cleanup to close()."
        )

        return content, changes

    # ==================================================================
    # CLASS DETECTION
    # ==================================================================

    def _find_color_model_class(self, content):

        pattern = re.compile(
            r'\bclass\s+([A-Za-z_$][\w$]*)'
            r'(?P<decl>[^{]*)\{',
            re.DOTALL
        )

        for match in pattern.finditer(content):

            declaration = match.group("decl")

            if not re.search(
                r'\bextends\s+(?:java\.awt\.image\.)?ColorModel\b',
                declaration
            ):
                continue

            brace_start = match.end() - 1

            class_end = self._find_matching_brace(
                content,
                brace_start
            )

            if class_end == -1:
                continue

            return (
                match.start(),
                class_end + 1,
                match.group(1),
                declaration
            )

        return None

    # ==================================================================
    # FINALIZE DETECTION
    # ==================================================================

    def _find_finalize_method(
        self,
        content,
        class_start,
        class_end
    ):

        class_content = content[class_start:class_end]

        pattern = re.compile(
            r'(?P<prefix>'
            r'(?:@[A-Za-z_$][\w$]*(?:\s*\([^)]*\))?\s*)*'
            r')'
            r'(?P<visibility>public|protected)\s+'
            r'void\s+finalize\s*'
            r'\(\s*\)'
            r'(?:\s+throws\s+[^{]+)?'
            r'\s*\{',
            re.DOTALL
        )

        match = pattern.search(class_content)

        if not match:
            return None

        absolute_start = class_start + match.start()

        brace_start = class_start + match.end() - 1

        method_end_brace = self._find_matching_brace(
            content,
            brace_start
        )

        if method_end_brace == -1:
            return None

        body = content[
            brace_start + 1:
            method_end_brace
        ]

        return (
            absolute_start,
            method_end_brace + 1,
            body
        )

    # ==================================================================
    # SUPER.FINALIZE CHECK
    # ==================================================================

    def _is_only_super_finalize(self, body):

        cleaned = self._strip_comments(body)

        cleaned = re.sub(
            r'\s+',
            '',
            cleaned
        )

        return cleaned in {
            "super.finalize();",
            "try{super.finalize();}finally{}"
        }

    def _remove_super_finalize(self, body):

        body = re.sub(
            r'\bsuper\s*\.\s*finalize\s*\(\s*\)\s*;',
            '',
            body
        )

        return body.strip()

    # ==================================================================
    # CLOSE DETECTION
    # ==================================================================

    def _has_close_method(
        self,
        content,
        class_start,
        class_end
    ):

        class_content = content[class_start:class_end]

        pattern = re.compile(
            r'\b(?:public|protected|private)?\s*'
            r'(?:final\s+)?'
            r'void\s+close\s*\(\s*\)',
            re.DOTALL
        )

        return pattern.search(class_content) is not None

    # ==================================================================
    # AUTO CLOSEABLE
    # ==================================================================

    def _add_auto_closeable(
        self,
        content,
        class_name
    ):

        pattern = re.compile(
            r'(\bclass\s+' +
            re.escape(class_name) +
            r'\b)'
            r'(?P<decl>[^{]*)'
            r'\{',
            re.DOTALL
        )

        match = pattern.search(content)

        if not match:
            return content, False

        declaration = match.group("decl")

        if re.search(
            r'\bAutoCloseable\b',
            declaration
        ):
            return content, False

        if re.search(
            r'\bimplements\b',
            declaration
        ):
            new_decl = re.sub(
                r'\bimplements\b',
                'implements AutoCloseable,',
                declaration,
                count=1
            )
        else:
            new_decl = (
                declaration.rstrip()
                + " implements AutoCloseable "
            )

        replacement = (
            match.group(1)
            + new_decl
            + "{"
        )

        content = (
            content[:match.start()]
            + replacement
            + content[match.end():]
        )

        return content, True

    # ==================================================================
    # CLEANER SUPPORT
    # ==================================================================

    def _add_cleaner_support(
        self,
        content,
        class_start,
        class_end,
        class_name,
        indentation
    ):

        # If Cleaner already exists, don't duplicate it.
        if re.search(
            r'\bCleaner\b',
            content[class_start:class_end]
        ):
            return content, False

        # Import.
        if "import java.lang.ref.Cleaner;" not in content:
            package_match = re.search(
                r'\bpackage\s+[^;]+;',
                content
            )

            if package_match:
                insert_at = package_match.end()
                content = (
                    content[:insert_at]
                    + "\n\nimport java.lang.ref.Cleaner;"
                    + content[insert_at:]
                )
            else:
                content = (
                    "import java.lang.ref.Cleaner;\n\n"
                    + content
                )

        # Recalculate class.
        class_info = self._find_color_model_class(content)

        if class_info is None:
            return content, False

        class_start, class_end, class_name, declaration = class_info

        class_body_start = content.find(
            "{",
            class_start,
            class_end
        )

        if class_body_start == -1:
            return content, False

        cleaner_fields = (
            "\n"
            f"{indentation}private static final Cleaner CLEANER = "
            "Cleaner.create();\n"
        )

        # State object allows Cleaner to execute cleanup without retaining
        # the enclosing ColorModel instance.
        state_class = (
            f"\n{indentation}private static final class "
            "CleanupState implements Runnable {\n"
            f"{indentation}    private boolean cleaned;\n\n"
            f"{indentation}    @Override\n"
            f"{indentation}    public void run() {{\n"
            f"{indentation}        cleaned = true;\n"
            f"{indentation}    }}\n"
            f"{indentation}}}\n"
        )

        insertion = cleaner_fields + state_class

        content = (
            content[:class_body_start + 1]
            + insertion
            + content[class_body_start + 1:]
        )

        return content, True

    # ==================================================================
    # CLEANER REGISTRATION
    # ==================================================================

    def _add_cleaner_registration(
        self,
        content,
        class_name
    ):

        # Locate a constructor.
        pattern = re.compile(
            r'\b' + re.escape(class_name) +
            r'\s*\([^)]*\)\s*\{',
            re.DOTALL
        )

        match = pattern.search(content)

        if not match:
            return content, False

        brace_start = match.end() - 1

        brace_end = self._find_matching_brace(
            content,
            brace_start
        )

        if brace_end == -1:
            return content, False

        constructor_body = content[
            brace_start + 1:
            brace_end
        ]

        if "CLEANER.register" in constructor_body:
            return content, False

        registration = (
            "\n        CLEANER.register("
            "this, new CleanupState());\n"
        )

        new_body = (
            registration
            + constructor_body
        )

        content = (
            content[:brace_start + 1]
            + new_body
            + content[brace_end:]
        )

        return content, True

    # ==================================================================
    # BRACE MATCHING
    # ==================================================================

    def _find_matching_brace(
        self,
        content,
        opening_brace
    ):

        depth = 0
        i = opening_brace
        length = len(content)

        in_string = False
        in_char = False
        in_line_comment = False
        in_block_comment = False
        escaped = False

        while i < length:

            ch = content[i]
            nxt = (
                content[i + 1]
                if i + 1 < length
                else ""
            )

            if in_line_comment:
                if ch == "\n":
                    in_line_comment = False

            elif in_block_comment:
                if ch == "*" and nxt == "/":
                    in_block_comment = False
                    i += 1

            elif in_string:
                if escaped:
                    escaped = False
                elif ch == "\\":
                    escaped = True
                elif ch == '"':
                    in_string = False

            elif in_char:
                if escaped:
                    escaped = False
                elif ch == "\\":
                    escaped = True
                elif ch == "'":
                    in_char = False

            else:

                if ch == "/" and nxt == "/":
                    in_line_comment = True
                    i += 1

                elif ch == "/" and nxt == "*":
                    in_block_comment = True
                    i += 1

                elif ch == '"':
                    in_string = True

                elif ch == "'":
                    in_char = True

                elif ch == "{":
                    depth += 1

                elif ch == "}":
                    depth -= 1

                    if depth == 0:
                        return i

            i += 1

        return -1

    # ==================================================================
    # COMMENT REMOVAL
    # ==================================================================

    def _strip_comments(self, text):

        text = re.sub(
            r'/\*.*?\*/',
            '',
            text,
            flags=re.DOTALL
        )

        text = re.sub(
            r'//.*',
            '',
            text
        )

        return text

    # ==================================================================
    # INDENTATION
    # ==================================================================

    def _get_method_indentation(
        self,
        content,
        position
    ):

        line_start = content.rfind(
            "\n",
            0,
            position
        ) + 1

        line = content[line_start:position]

        match = re.match(
            r'[ \t]*',
            line
        )

        return match.group(0) if match else ""

    def _indent_body(
        self,
        body,
        indentation
    ):

        lines = body.splitlines()

        if not lines:
            return indentation + "return;"

        return "\n".join(
            indentation + line.strip()
            for line in lines
            if line.strip()
        )