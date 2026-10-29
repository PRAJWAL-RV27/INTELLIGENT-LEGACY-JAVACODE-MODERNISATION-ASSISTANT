import re


class RemoveIfTransformer:
    name = "Iterator removal loop -> removeIf()"

    def transform(self, content):
        pattern = re.compile(
            r'(\w+)\.removeIf\s*\('
        )

        # Only handles the simple, direct iterator-removal pattern.
        loop_pattern = re.compile(
            r'java\.util\.Iterator<[^>]+>\s+(\w+)\s*=\s*(\w+)\.iterator\(\)\s*;\s*'
            r'while\s*\(\s*\1\.hasNext\(\)\s*\)\s*\{\s*'
            r'(\w+)\s+\w+\s*=\s*\1\.next\(\)\s*;\s*'
            r'if\s*\((.*?)\)\s*\{\s*\1\.remove\(\)\s*;\s*\}\s*\}'
        )

        def replace(match):
            iterator, collection, variable, condition = match.groups()
            condition = re.sub(
                rf'\b{re.escape(variable)}\b',
                "item",
                condition
            )
            return f"{collection}.removeIf(item -> {condition});"

        updated, changes = loop_pattern.subn(replace, content)
        return updated, changes