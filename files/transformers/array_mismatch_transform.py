
import re


class ArraysMismatchTransformer:
    NAME = "Manual int[] equality loop -> Arrays.mismatch()"

    def transform(self, content: str):
        changes = []

        pattern = re.compile(
            r"(?P<sig>\bboolean\s+(?P<method>[A-Za-z_$]\w*)\s*\(\s*"
            r"int\s*\[\s*\]\s*(?P<a>[A-Za-z_$]\w*)\s*,\s*"
            r"int\s*\[\s*\]\s*(?P<b>[A-Za-z_$]\w*)\s*\)\s*\{)\s*"
            r"if\s*\(\s*(?P=a)\.length\s*!=\s*(?P=b)\.length\s*\)\s*"
            r"return\s+false\s*;\s*"
            r"for\s*\(\s*int\s+(?P<i>[A-Za-z_$]\w*)\s*=\s*0\s*;\s*"
            r"(?P=i)\s*<\s*(?P=a)\.length\s*;\s*(?P=i)\+\+\s*\)\s*\{\s*"
            r"if\s*\(\s*(?P=a)\s*\[\s*(?P=i)\s*\]\s*!=\s*"
            r"(?P=b)\s*\[\s*(?P=i)\s*\]\s*\)\s*return\s+false\s*;\s*\}\s*"
            r"return\s+true\s*;\s*\}",
            re.MULTILINE,
        )

        def replace(match):
            a = match.group("a")
            b = match.group("b")

            changes.append(
                f"Replaced manual int[] equality check with Arrays.mismatch({a}, {b})"
            )

            return (
                f"{match.group('sig')}\n"
                f"    return java.util.Arrays.mismatch({a}, {b}) == -1;\n"
                f"}}"
            )

        updated_content = pattern.sub(replace, content)
        return updated_content, changes
