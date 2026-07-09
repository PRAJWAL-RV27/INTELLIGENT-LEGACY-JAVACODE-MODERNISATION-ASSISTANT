import re
from .base_transformer import BaseTransformer


class TextLayoutHashCodeTransformer(BaseTransformer):

    def transform(self, code: str) -> tuple[str, list[str]]:
        changes: list[str] = []

        # ✅ Step 1: Ensure TextLayout is used
        if "import java.awt.font.TextLayout" not in code:
            return code, changes

        # ✅ Step 2: Find TextLayout variables
        var_pattern = re.compile(r'TextLayout\s+(\w+)')
        textlayout_vars = set(var_pattern.findall(code))

        if not textlayout_vars:
            return code, changes

        # ✅ Step 3: Find .hashCode() calls
        pattern = re.compile(r'(\w+)\.hashCode\(\)')

        def replacer(match):
            obj = match.group(1)

            # ✅ Only replace if it's a TextLayout variable
            if obj in textlayout_vars:
                replacement = f"System.identityHashCode({obj})"

                changes.append(
                    f"Replaced TextLayout.hashCode(): {obj}.hashCode() → {replacement}"
                )

                return replacement

            return match.group(0)

        new_code = pattern.sub(replacer, code)

        return new_code, changes