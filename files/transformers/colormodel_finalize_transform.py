import re
from .base_transformer import BaseTransformer


class ColorModelFinalizeTransformer(BaseTransformer):

    def transform(self, content: str):

        changes = []

        if "extends ColorModel" not in content:
            return content, changes

        pattern = re.compile(
            r'((?:@\w+(?:\(.*?\))?\s*)*)'
            r'(public|protected)\s+void\s+finalize\s*\(\s*\)'
            r'(?:\s*throws\s+[^{]+)?\s*\{',
            re.DOTALL
        )

        match = pattern.search(content)

        if not match:
            return content, changes

        method_start = match.start()

        brace_start = content.find("{", match.end() - 1)

        depth = 1
        i = brace_start + 1

        while i < len(content):

            if content[i] == "{":
                depth += 1

            elif content[i] == "}":
                depth -= 1

                if depth == 0:
                    break

            i += 1

        method_end = i + 1

        body = content[brace_start + 1:i].strip()

        cleaned = re.sub(r"\s+", "", body)

        # Empty finalize

        if cleaned == "":

            content = content[:method_start] + content[method_end:]

            changes.append("Removed empty ColorModel.finalize().")

            return content, changes

        # Only super.finalize()

        if cleaned == "super.finalize();":

            content = content[:method_start] + content[method_end:]

            changes.append("Removed redundant ColorModel.finalize().")

            return content, changes

        # Cleanup logic exists

        body = body.replace("@Override", "").strip()

        new_method = (
            "\n    @Override\n"
            "    public void close() {\n"
            f"        {body}\n"
            "    }\n"
        )

        content = (
            content[:method_start]
            + new_method
            + content[method_end:]
        )

        # Add AutoCloseable

        class_pattern = re.compile(
            r'class\s+(\w+)([^{]*)\{'
        )

        cls = class_pattern.search(content)

        if cls:

            declaration = cls.group(0)

            if "AutoCloseable" not in declaration:

                before_brace = declaration[:-1].rstrip()

                if "implements" in before_brace:

                    before_brace += ", AutoCloseable"

                else:

                    before_brace += " implements AutoCloseable"

                new_decl = before_brace + " {"

                content = (
                    content[:cls.start()]
                    + new_decl
                    + content[cls.end():]
                )

                changes.append(
                    "Added AutoCloseable."
                )

        changes.append(
            "Converted ColorModel.finalize() to close()."
        )

        return content, changes