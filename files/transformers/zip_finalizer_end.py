import re
from .base_transformer import BaseTransformer


class ZipFinalizerEndTransformer(BaseTransformer):
    def transform(self, content: str) -> tuple[str, list[str]]:
        result = content
        changes: list[str] = []

        known_types_by_name: dict[str, str] = {}
        for match in re.finditer(
            r'\b(?:java\.util\.zip\.)?(Deflater|Inflater)\s+([A-Za-z_]\w*)\b',
            result,
        ):
            known_types_by_name[match.group(2)] = match.group(1)

        def replace_variable_call(match: re.Match[str]) -> str:
            name = match.group("name")
            type_name = known_types_by_name.get(name)
            if type_name is None:
                return match.group(0)

            replacement = f"{name}{match.group('dot')}end{match.group('parens')}"
            changes.append(
                f"Original API: {type_name}.finalize(); Replacement API: {type_name}.end(); Reason: Java finalization removal"
            )
            return replacement

        result = re.sub(
            r'(?P<name>\b[A-Za-z_]\w*\b)(?P<dot>\s*\.\s*)finalize(?P<parens>\s*\(\s*\))',
            replace_variable_call,
            result,
        )

        def replace_constructor_call(match: re.Match[str]) -> str:
            type_name = match.group("type")
            replacement = (
                f"{match.group('receiver')}{match.group('dot')}end{match.group('parens')}"
            )
            changes.append(
                f"Original API: {type_name}.finalize(); Replacement API: {type_name}.end(); Reason: Java finalization removal"
            )
            return replacement

        result = re.sub(
            r'(?P<receiver>new\s+(?:java\.util\.zip\.)?(?P<type>Deflater|Inflater)\s*\([^)]*\))(?P<dot>\s*\.\s*)finalize(?P<parens>\s*\(\s*\))',
            replace_constructor_call,
            result,
        )

        return result, changes
