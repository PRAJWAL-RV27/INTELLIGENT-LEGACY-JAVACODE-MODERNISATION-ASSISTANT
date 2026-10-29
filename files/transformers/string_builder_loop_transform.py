import re


class StringBuilderLoopTransformer:
    NAME = "Repeated string concatenation -> StringBuilder"
    name = NAME

    def transform(self, content):
        pattern = re.compile(
            r'for\s*\(\s*int\s+(\w+)\s*=\s*0\s*;\s*'
            r'\1\s*<\s*(\w+)\.length\(\)\s*;\s*'
            r'\1\+\+\s*\)\s*\{\s*'
            r'(\w+)\s*\+=\s*\2\.charAt\(\s*\1\s*\)\s*;\s*\}'
        )

        def replace(match):
            index, source, target = match.groups()
            return (
                f"StringBuilder builder = new StringBuilder({target});\n"
                f"for (int {index} = 0; {index} < {source}.length(); "
                f"{index}++) {{\n"
                f"    builder.append({source}.charAt({index}));\n"
                f"}}\n"
                f"{target} = builder.toString();"
            )

        updated, changes = pattern.subn(replace, content)
        return updated, changes