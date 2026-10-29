import re


class StringFormattedTransformer:
    NAME = "String.format() -> String.formatted()"
    name = NAME

    def transform(self, content):
        pattern = re.compile(
            r'String\.format\(\s*("(?:[^"\\]|\\.)*")\s*,\s*'
            r'([^;()]+?)\s*\)'
        )
        updated, changes = pattern.subn(
            r'(\1).formatted(\2)', content
        )
        return updated, changes