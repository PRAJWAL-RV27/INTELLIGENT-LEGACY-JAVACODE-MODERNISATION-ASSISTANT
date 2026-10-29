import re


class ByteArrayWriteToTransformer:
    NAME = "ByteArrayOutputStream copy -> writeTo()"
    name = NAME

    def transform(self, content):
        pattern = re.compile(
            r'(\w+)\.write\(\s*(\w+)\.toByteArray\(\)\s*\)\s*;'
        )

        def replace(match):
            output_stream, buffer_stream = match.groups()
            return f"{buffer_stream}.writeTo({output_stream});"

        updated, changes = pattern.subn(replace, content)
        return updated, changes