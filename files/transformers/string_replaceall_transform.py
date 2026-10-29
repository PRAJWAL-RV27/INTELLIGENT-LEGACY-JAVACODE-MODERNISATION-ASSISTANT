import re


class StringReplaceAllTransformer:
    """
    Converts replaceAll() to replace() when the search string
    is a compile-time literal containing no regex metacharacters.

    Example:

        text.replaceAll("abc", "xyz");

    becomes:

        text.replace("abc", "xyz");

    This avoids regex processing while preserving literal replacement
    semantics for the supported cases.
    """

    NAME = "String.replaceAll() -> String.replace()"

    REGEX_META = set(r"\.^$|()[]{}*+")

    def transform(self, content: str):
        changes = []

        pattern = re.compile(
            r'(?P<object>\b[A-Za-z_$][\w$]*(?:\.[A-Za-z_$][\w$]*)*)'
            r'\.replaceAll\('
            r'"(?P<search>[^"\\]*)"\s*,\s*'
            r'"(?P<replacement>[^"\\]*)"'
            r'\)'
        )

        def replace(match):
            obj = match.group("object")
            search = match.group("search")
            replacement = match.group("replacement")

            # Only transform plain literal strings.
            if any(char in self.REGEX_META for char in search):
                return match.group(0)

            changes.append(
                f"Replaced {obj}.replaceAll(\"{search}\", "
                f"\"{replacement}\") with replace()"
            )

            return (
                f'{obj}.replace("{search}", "{replacement}")'
            )

        transformed = pattern.sub(replace, content)

        return transformed, changes