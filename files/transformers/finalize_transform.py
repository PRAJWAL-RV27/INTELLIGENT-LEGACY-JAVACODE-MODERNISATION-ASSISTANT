import re
from .base_transformer import BaseTransformer


class FinalizeTransformer(BaseTransformer):

    def transform(self, content: str):

        changes = []

        # Skip ColorModel subclasses
        if "extends ColorModel" in content:
            return content, changes

        pattern = re.compile(
            r'((?:@\w+(?:\(.*?\))?\s*)*)'
            r'(public|protected)\s+void\s+finalize\s*\(\s*\)'
            r'(?:\s*throws\s+[^{]+)?\s*\{',
            re.DOTALL
        )

        while True:

            match = pattern.search(content)

            if not match:
                break

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

            # Case 1 : Empty finalize()

            if cleaned == "":

                content = content[:method_start] + content[method_end:]

                changes.append("Removed empty finalize().")

                continue

            # Case 2 : only super.finalize()

            if cleaned == "super.finalize();":

                content = content[:method_start] + content[method_end:]

                changes.append("Removed redundant finalize().")

                continue

            # Case 3 : Non-empty finalize()

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

            changes.append(
                "Converted finalize() to close(). Implement AutoCloseable manually if required."
            )

        return content, changes