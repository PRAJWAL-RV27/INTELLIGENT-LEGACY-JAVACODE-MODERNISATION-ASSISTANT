import re


class StringBuilderIsEmptyTransformer:
    NAME = "StringBuilder.length() == 0 -> isEmpty()"
    name = NAME

    def transform(self, content):
        pattern = re.compile(
            r'\b(\w+)\.length\(\)\s*==\s*0'
        )
        updated, changes = pattern.subn(
            r'\1.isEmpty()', content
        )
        return updated, changes