import re


class OptionalIsEmptyTransformer:
    NAME = "!Optional.isPresent() -> Optional.isEmpty()"
    name = NAME

    def transform(self, content):
        pattern = re.compile(
            r'!\s*(\w+)\.isPresent\(\)'
        )
        updated, changes = pattern.subn(
            r'\1.isEmpty()', content
        )
        return updated, changes