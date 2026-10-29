import re


class FilesReadStringTransformer:
    NAME = "Files.readAllBytes() -> Files.readString()"
    name = NAME

    def transform(self, content):
        pattern = re.compile(
            r'new\s+String\(\s*'
            r'Files\.readAllBytes\(\s*(\w+)\s*\)\s*,\s*'
            r'StandardCharsets\.UTF_8\s*\)'
        )
        updated, changes = pattern.subn(
            r'Files.readString(\1, StandardCharsets.UTF_8)',
            content
        )
        return updated, changes