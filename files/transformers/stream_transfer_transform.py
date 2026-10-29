import re


class StreamTransferTransformer:
    NAME = "InputStream copy loop -> transferTo()"
    name = NAME

    def transform(self, content):
        pattern = re.compile(
            r'while\s*\(\s*\(\s*(\w+)\s*=\s*(\w+)\.read\(\s*'
            r'(\w+)\s*\)\s*\)\s*!=\s*-1\s*\)\s*\{\s*'
            r'(\w+)\.write\(\s*\3\s*,\s*0\s*,\s*\1\s*\)\s*;\s*\}'
        )

        def replace(match):
            count, source, buffer, destination = match.groups()
            if count != match.group(1):
                return match.group(0)
            return f"{source}.transferTo({destination});"

        updated, changes = pattern.subn(replace, content)
        return updated, changes