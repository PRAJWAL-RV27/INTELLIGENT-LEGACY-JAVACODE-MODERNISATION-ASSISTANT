import re
from .base_transformer import BaseTransformer

class JAXBHelpersRemovalTransformer(BaseTransformer):

    def transform(self, content: str) -> tuple[str, list[str]]:
        changes: list[str] = []

        # 1. Replace helpers package with jakarta
        new_content = re.sub(
            r'import\s+javax\.xml\.bind\.helpers\.',
            'import jakarta.xml.bind.helpers.',
            content
        )
        if new_content != content:
            changes.append("Replaced javax.xml.bind.helpers with jakarta.xml.bind.helpers")
        content = new_content

        # 2. Add migration comment if JAXB helpers are used
        if "jakarta.xml.bind.helpers" in content:
            if "JAXB helpers requires dependency" not in content:
                content = (
                    "// JAVA21-MIGRATION: Add dependency: jakarta.xml.bind:jakarta.xml.bind-api\n"
                    + content
                )
                changes.append("Added JAXB helpers dependency comment")

        return content, changes