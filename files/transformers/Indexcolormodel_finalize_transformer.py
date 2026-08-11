import re
from .base_transformer import BaseTransformer


class IndexColorModelFinalizeTransformer(BaseTransformer):

    def transform(self, content: str):
        changes = []

        # Only process subclasses of IndexColorModel
        if "extends IndexColorModel" not in content:
            return content, changes

        # ---------------------------------------------------
        # Add implements AutoCloseable
        # ---------------------------------------------------
        class_pattern = re.compile(
            r'(public\s+class\s+\w+\s+extends\s+IndexColorModel)(?![^{]*implements)'
        )

        if class_pattern.search(content):
            content = class_pattern.sub(
                r'\1 implements AutoCloseable',
                content,
                count=1,
            )
            changes.append(
                "Added AutoCloseable to IndexColorModel subclass."
            )

        # ---------------------------------------------------
        # Replace finalize() declaration
        # ---------------------------------------------------
        finalize_pattern = re.compile(
            r'@Override\s+protected\s+void\s+finalize\s*\(\s*\)\s*(?:throws\s+Throwable\s*)?\{',
            re.MULTILINE,
        )

        if finalize_pattern.search(content):
            content = finalize_pattern.sub(
                "@Override\n    public void close() {",
                content,
                count=1,
            )

            changes.append(
                "Replaced finalize() with close()."
            )

        # ---------------------------------------------------
        # Remove super.finalize();
        # ---------------------------------------------------
        if "super.finalize();" in content:
            content = content.replace(
                "super.finalize();",
                ""
            )

            changes.append(
                "Removed super.finalize() call."
            )

        # ---------------------------------------------------
        # Remove empty finally block if present
        # ---------------------------------------------------
        content = re.sub(
            r'finally\s*\{\s*\}',
            "",
            content
        )

        return content, changes