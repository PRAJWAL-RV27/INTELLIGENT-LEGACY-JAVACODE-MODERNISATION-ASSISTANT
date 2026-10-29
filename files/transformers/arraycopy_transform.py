
import re


class ArrayCopyTransformer:
    NAME = "Manual array copy loop -> System.arraycopy()"

    def transform(self, content: str):
        changes = []

        pattern = re.compile(
            r"for\s*\(\s*int\s+(?P<i>[A-Za-z_$]\w*)\s*=\s*0\s*;\s*"
            r"(?P=i)\s*<\s*(?P<src>[A-Za-z_$]\w*)\.length\s*;\s*"
            r"(?P=i)\s*\+\+\s*\)\s*\{\s*"
            r"(?P<dst>[A-Za-z_$]\w*)\s*\[\s*(?P=i)\s*\]\s*=\s*"
            r"(?P=src)\s*\[\s*(?P=i)\s*\]\s*;\s*\}",
            re.MULTILINE,
        )

        def replace(match):
            src = match.group("src")
            dst = match.group("dst")

            changes.append(
                f"Replaced array copy loop with System.arraycopy({src}, 0, {dst}, 0, {src}.length)"
            )

            return (
                f"System.arraycopy({src}, 0, {dst}, 0, {src}.length);"
            )

        updated_content = pattern.sub(replace, content)
        return updated_content, changes
