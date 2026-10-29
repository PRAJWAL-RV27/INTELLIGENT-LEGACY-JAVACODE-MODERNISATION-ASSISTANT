import re


class StringMatchesEqualsTransformer:
    """
    Converts String.matches() to String.equals() when the supplied
    regex is a plain literal string.

    Example:

        name.matches("Pavitra")

    becomes:

        name.equals("Pavitra")

    Only literal patterns are transformed.
    """

    NAME = "String.matches() -> String.equals()"

    REGEX_META = set(r"\.^$|()[]{}*+")

    def transform(self, content: str):
        changes = []

        pattern = re.compile(
            r'(?P<object>\b[A-Za-z_$][\w$]*(?:\.[A-Za-z_$][\w$]*)*)'
            r'\.matches\('
            r'"(?P<value>[^"\\]*)"'
            r'\)'
        )

        def replace(match):
            obj = match.group("object")
            value = match.group("value")

            # matches() interprets its argument as regex.
            # Only replace when it is a plain literal.
            if any(char in self.REGEX_META for char in value):
                return match.group(0)

            changes.append(
                f'Replaced {obj}.matches("{value}") with equals()'
            )

            return f'{obj}.equals("{value}")'

        transformed = pattern.sub(replace, content)

        return transformed, changes