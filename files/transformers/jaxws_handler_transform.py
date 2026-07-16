import re
from .base_transformer import BaseTransformer


class JAXWSHandlerTransformer(BaseTransformer):

    def transform(self, content: str) -> tuple[str, list[str]]:
        changes = []
        original = content

        lines = content.split("\n")
        new_lines = []

        for line in lines:
            stripped = line.strip()

            if stripped.startswith("//"):
                new_lines.append(line)
                continue

            if stripped.startswith("import javax.xml.ws.handler."):
                import_path = stripped[len("import "):].rstrip(";").strip()

                replaced = line.replace(
                    "import javax.xml.ws.handler.",
                    "import jakarta.xml.ws.handler."
                )

                new_lines.append(replaced)

                changes.append(
                    f"Replaced JAX-WS handler import `{import_path}` with Jakarta equivalent"
                )
                continue

            new_lines.append(line)

        content = "\n".join(new_lines)

        new_content = re.sub(
            r'\bjavax\.xml\.ws\.handler\.',
            'jakarta.xml.ws.handler.',
            content
        )

        if new_content != content:
            changes.append(
                "Replaced javax.xml.ws.handler package references with jakarta.xml.ws.handler"
            )

        content = new_content

        migration_comment = (
            "// JAVA21-MIGRATION: javax.xml.ws.handler was removed from the JDK in Java 11. "
            "Use Jakarta XML Web Services API "
            "(jakarta.xml.ws:jakarta.xml.ws-api)."
        )

        if (
            "jakarta.xml.ws.handler" in content
            and migration_comment not in content
        ):
            content = migration_comment + "\n" + content
            changes.append("Added JAX-WS handler migration dependency comment")

        content = re.sub(r"\n{3,}", "\n\n", content)

        if content == original:
            return content, []

        return content, changes