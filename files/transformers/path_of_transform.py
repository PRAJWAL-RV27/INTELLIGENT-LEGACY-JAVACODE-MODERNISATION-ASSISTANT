import re


class PathOfTransformer:
    NAME = "Paths.get() -> Path.of()"
    name = NAME

    def transform(self, content):
        pattern = re.compile(
            r'\bPaths\.get\(\s*("(?:[^"\\]|\\.)*")\s*\)'
        )
        updated, changes = pattern.subn(r'Path.of(\1)', content)
        return updated, changes