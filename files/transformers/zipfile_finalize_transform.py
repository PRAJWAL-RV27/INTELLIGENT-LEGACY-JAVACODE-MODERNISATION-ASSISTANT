import re

from .base_transformer import BaseTransformer


class ZipFileFinalizeTransformer(BaseTransformer):
    """Replace java.util.zip.ZipFile.finalize() with close()."""

    def transform(self, content: str) -> tuple[str, list[str]]:
        result = content
        changes: list[str] = []

        # Track variables whose declared type is exactly ZipFile.
        zipfile_vars: set[str] = set()

        declaration_pattern = (
            r"\b(?:java\.util\.zip\.)?ZipFile\s+"
            r"([A-Za-z_]\w*)\b"
        )

        for match in re.finditer(declaration_pattern, result):
            zipfile_vars.add(match.group(1))

        # ---------------------------------------------------------
        # 1. ZipFile variable.finalize() -> variable.close()
        # ---------------------------------------------------------

        def replace_variable_call(match: re.Match[str]) -> str:
            var_name = match.group("name")

            # CRITICAL:
            # Do not touch unknown/unrelated finalize() calls.
            if var_name not in zipfile_vars:
                return match.group(0)

            replacement = (
                f"{var_name}"
                f"{match.group('dot')}"
                f"close"
                f"{match.group('parens')}"
            )

            changes.append(
                "Original API: ZipFile.finalize(); "
                "Replacement API: ZipFile.close(); "
                "Reason: Java finalization removal"
            )

            return replacement

        result = re.sub(
            r"(?P<name>\b[A-Za-z_]\w*\b)"
            r"(?P<dot>\s*\.\s*)"
            r"finalize"
            r"(?P<parens>\s*\(\s*\))",
            replace_variable_call,
            result,
        )

        # ---------------------------------------------------------
        # 2. new ZipFile(...).finalize() -> new ZipFile(...).close()
        # ---------------------------------------------------------

        def replace_constructor_call(match: re.Match[str]) -> str:
            replacement = (
                f"{match.group('receiver')}"
                f"{match.group('dot')}"
                f"close"
                f"{match.group('parens')}"
            )

            changes.append(
                "Original API: ZipFile.finalize(); "
                "Replacement API: ZipFile.close(); "
                "Reason: Java finalization removal"
            )

            return replacement

        result = re.sub(
            r"(?P<receiver>"
            r"new\s+(?:java\.util\.zip\.)?ZipFile"
            r"\s*\([^)]*\)"
            r")"
            r"(?P<dot>\s*\.\s*)"
            r"finalize"
            r"(?P<parens>\s*\(\s*\))",
            replace_constructor_call,
            result,
        )

        return result, changes
