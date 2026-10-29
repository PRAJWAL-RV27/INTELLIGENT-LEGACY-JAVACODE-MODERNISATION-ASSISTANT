import re


class StringBuilderAppendValueOfTransformer:
    """
    Converts:

        builder.append(String.valueOf(value));

    to:

        builder.append(value);

    This removes an unnecessary explicit String.valueOf() call.
    """

    NAME = "StringBuilder.append(String.valueOf()) -> append()"

    def transform(self, content: str):
        changes = []

        pattern = re.compile(
            r'(?P<builder>\b[A-Za-z_$][\w$]*)'
            r'\.append\('
            r'String\.valueOf\('
            r'(?P<value>[A-Za-z_$][\w$]*)'
            r'\)'
            r'\)'
        )

        def replace(match):
            builder = match.group("builder")
            value = match.group("value")

            changes.append(
                f"Replaced {builder}.append(String.valueOf({value})) "
                f"with {builder}.append({value})"
            )

            return f"{builder}.append({value})"

        transformed = pattern.sub(replace, content)

        return transformed, changes