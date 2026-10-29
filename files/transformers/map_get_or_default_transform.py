import re


class MapGetOrDefaultTransformer:
    name = "Map containsKey + get -> getOrDefault()"

    def transform(self, content):
        pattern = re.compile(
            r'if\s*\(\s*(\w+)\.containsKey\(\s*(\w+)\s*\)\s*\)\s*\{\s*'
            r'(\w+)\s*=\s*\1\.get\(\s*\2\s*\)\s*;\s*'
            r'\}\s*else\s*\{\s*'
            r'\3\s*=\s*([^;]+)\s*;\s*\}'
        )

        def replace(match):
            map_name, key, variable, default_value = match.groups()
            return (
                f"{variable} = {map_name}.getOrDefault("
                f"{key}, {default_value.strip()});"
            )

        updated, changes = pattern.subn(replace, content)
        return updated, changes