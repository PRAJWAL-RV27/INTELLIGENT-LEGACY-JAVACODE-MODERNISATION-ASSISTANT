import re


class CollectionEmptyTransformer:
    NAME = "Collection.size()==0 -> isEmpty()"

    def transform(self, content: str):
        changes = []

        pattern = re.compile(
            r'(\b[A-Za-z_$][\w$]*)\.size\(\)\s*==\s*0'
        )

        def replace(match):
            variable = match.group(1)
            changes.append(
                f"Replaced {variable}.size() == 0 with {variable}.isEmpty()"
            )
            return f"{variable}.isEmpty()"

        transformed = pattern.sub(replace, content)

        return transformed, changes