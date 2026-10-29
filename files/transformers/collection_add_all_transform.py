import re


class CollectionAddAllTransformer:
    NAME = "Element insertion loop -> addAll()"
    name = NAME

    def transform(self, content):
        pattern = re.compile(
            r'for\s*\(\s*(?:\w+\s+)?(\w+)\s*:\s*(\w+)\s*\)\s*\{\s*'
            r'(\w+)\.add\(\s*\1\s*\)\s*;\s*\}'
        )

        def replace(match):
            variable, source, destination = match.groups()
            return f"{destination}.addAll({source});"

        updated, changes = pattern.subn(replace, content)
        return updated, changes