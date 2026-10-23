import re
from .base_transformer import BaseTransformer, add_import


class JAXBBindTransformer(BaseTransformer):

    def transform(self, content: str) -> tuple[str, list[str]]:
        changes: list[str] = []
        original = content

        # ---------------------------------------------------------
        # 1. Replace import javax.xml.bind.* -> import jakarta.xml.bind.*
        #    But do NOT keep DatatypeConverter import, because we convert
        #    its call-sites to java.util.Base64 instead.
        # ---------------------------------------------------------
        lines = content.split("\n")
        new_lines: list[str] = []
        base64_needed = False
        dependency_needed = False

        for line in lines:
            stripped = line.strip()

            # Ignore already commented lines
            if stripped.startswith("//"):
                new_lines.append(line)
                continue

            if stripped.startswith("import javax.xml.bind."):
                import_path = stripped[len("import "):].rstrip(";").strip()

                # Special case: DatatypeConverter -> Base64
                if import_path == "javax.xml.bind.DatatypeConverter":
                    base64_needed = True
                    changes.append(
                        "Removed javax.xml.bind.DatatypeConverter import and will use java.util.Base64"
                    )
                    continue

                # General JAXB package migration
                replaced_line = line.replace(
                    "import javax.xml.bind.",
                    "import jakarta.xml.bind."
                )
                if replaced_line != line:
                    new_lines.append(replaced_line)
                    dependency_needed = True
                    changes.append(
                        f"Replaced JAXB import `{import_path}` with Jakarta equivalent"
                    )
                    continue

            new_lines.append(line)

        content = "\n".join(new_lines)

        # ---------------------------------------------------------
        # 2. Replace DatatypeConverter usage with Base64
        # ---------------------------------------------------------
        new_content = re.sub(
            r'\bDatatypeConverter\.parseBase64Binary\s*\((.*?)\)',
            r'Base64.getDecoder().decode(\1)',
            content
        )
        if new_content != content:
            changes.append(
                "Replaced DatatypeConverter.parseBase64Binary(...) with Base64.getDecoder().decode(...)"
            )
            base64_needed = True
        content = new_content

        new_content = re.sub(
            r'\bDatatypeConverter\.printBase64Binary\s*\((.*?)\)',
            r'Base64.getEncoder().encodeToString(\1)',
            content
        )
        if new_content != content:
            changes.append(
                "Replaced DatatypeConverter.printBase64Binary(...) with Base64.getEncoder().encodeToString(...)"
            )
            base64_needed = True
        content = new_content

        # ---------------------------------------------------------
        # 3. If raw javax.xml.bind references still remain in code text,
        #    replace package usage with jakarta.xml.bind.
        #    Example:
        #      javax.xml.bind.JAXBContext.newInstance(...)
        #      -> jakarta.xml.bind.JAXBContext.newInstance(...)
        # ---------------------------------------------------------
        new_content = re.sub(
            r'\bjavax\.xml\.bind\.',
            'jakarta.xml.bind.',
            content
        )
        if new_content != content:
            changes.append("Replaced javax.xml.bind package references with jakarta.xml.bind")
            dependency_needed = True
        content = new_content

        # ---------------------------------------------------------
        # 4. Add import java.util.Base64 if needed
        # ---------------------------------------------------------
        if base64_needed and "import java.util.Base64;" not in content:
            content = add_import(content, "java.util.Base64")
            changes.append("Added import java.util.Base64")

        # ---------------------------------------------------------
        # 5. Add ONE migration comment if Jakarta JAXB is now used
        # ---------------------------------------------------------
        migration_comment = (
            "// JAVA21-MIGRATION: javax.xml.bind (JAXB) was removed from the JDK in Java 11 (JEP 320). "
            "Use Jakarta JAXB and add dependency: jakarta.xml.bind:jakarta.xml.bind-api"
        )

        if (
            ("jakarta.xml.bind" in content)
            and (migration_comment not in content)
        ):
            content = migration_comment + "\n" + content
            changes.append("Added JAXB migration dependency comment")

        # ---------------------------------------------------------
        # 6. Deduplicate blank lines caused by removed imports
        # ---------------------------------------------------------
        content = re.sub(r'\n{3,}', '\n\n', content)

        if content == original:
            return content, []

        return content, changes
