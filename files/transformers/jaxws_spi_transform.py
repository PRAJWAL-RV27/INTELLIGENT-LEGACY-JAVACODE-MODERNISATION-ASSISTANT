import re


class JAXWSSPITransformer:
    """
    Transformer for:

        import javax.xml.ws.spi.*

    Removed from JDK in Java 11 (JEP 320).
    """

    IMPORT_PATTERN = re.compile(
        r'^\s*import\s+javax\.xml\.ws\.spi\.([A-Za-z_][A-Za-z0-9_]*)\s*;',
        re.MULTILINE
    )

    def transform(self, content: str):

        changes = []

        imported_classes = []

        # ---------------------------------------------------------
        # Find deprecated imports
        # ---------------------------------------------------------

        matches = list(self.IMPORT_PATTERN.finditer(content))

        for match in reversed(matches):

            class_name = match.group(1)

            imported_classes.append(class_name)

            replacement = (
                "// ==========================================================\n"
                "// TODO(Java21)\n"
                "// javax.xml.ws.spi removed from JDK in Java 11.\n"
                "// JEP 320 : Remove the Java EE and CORBA Modules.\n"
                "// Consider migrating to Jakarta XML Web Services.\n"
                "// Manual migration required.\n"
                "//\n"
                f"// {match.group(0).strip()}\n"
                "// =========================================================="
            )

            content = (
                content[:match.start()]
                + replacement
                + content[match.end():]
            )

            changes.append(
                f"Removed javax.xml.ws.spi import '{class_name}'."
            )

        # ---------------------------------------------------------
        # Find usages
        # ---------------------------------------------------------

        for class_name in imported_classes:

            usage_pattern = re.compile(
                r"\b" + re.escape(class_name) + r"\b"
            )

    # Prevent duplicate reporting on the same line
            reported_lines = set()

            for occurrence in usage_pattern.finditer(content):

                line_number = (
                    content[:occurrence.start()].count("\n") + 1
                )

                if line_number in reported_lines:
                    continue

                reported_lines.add(line_number)

                line_text = (
                    content.splitlines()[line_number - 1].strip()
                )

                if line_text.startswith("//"):
                        continue

                changes.append(
                    f"Manual migration required: "
                    f"'{class_name}' used at line {line_number}."
                )

        return content, changes