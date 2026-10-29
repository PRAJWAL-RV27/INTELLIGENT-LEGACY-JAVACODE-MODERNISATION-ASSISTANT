import re


class CollectionsSortTransformer:
    """
    Converts:

        Collections.sort(list);

    to:

        list.sort(null);

    Only the no-comparator form is transformed.

    The optimizer subsequently benchmarks the original and
    transformed versions before deciding whether to apply it.
    """

    NAME = "Collections.sort() -> List.sort(null)"

    def transform(self, content: str):
        changes = []

        pattern = re.compile(
            r'\bCollections\.sort\('
            r'(?P<list>[A-Za-z_$][\w$]*)'
            r'\)\s*;'
        )

        def replace(match):
            collection = match.group("list")

            changes.append(
                f"Replaced Collections.sort({collection}) "
                f"with {collection}.sort(null)"
            )

            return f'{collection}.sort(null);'

        transformed = pattern.sub(replace, content)

        return transformed, changes