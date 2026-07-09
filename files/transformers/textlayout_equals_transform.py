import re
from .base_transformer import BaseTransformer


class TextLayoutEqualsTransformer(BaseTransformer):

    def transform(self, code: str) -> tuple[str, list[str]]:
        changes: list[str] = []

        # ✅ Step 1: Ensure TextLayout is actually used
        if "import java.awt.font.TextLayout" not in code:
            return code, changes

        # ✅ Step 2: Find variables declared as TextLayout
        # Example: TextLayout t1 = ...
        var_pattern = re.compile(r'TextLayout\s+(\w+)')
        textlayout_vars = set(var_pattern.findall(code))

        if not textlayout_vars:
            return code, changes

        # ✅ Step 3: Replace ONLY when both variables are TextLayout
        pattern = re.compile(r'(\w+)\.equals\((\w+)\)')

        def replacer(match):
            obj1 = match.group(1)
            obj2 = match.group(2)

            # ✅ Only replace if both are TextLayout variables
            if obj1 in textlayout_vars and obj2 in textlayout_vars:
                replacement = f"{obj1} == {obj2}"

                changes.append(
                    f"Replaced TextLayout.equals(): {obj1}.equals({obj2}) → {replacement}"
                )

                return replacement

            # ❌ Otherwise keep original
            return match.group(0)

        new_code = pattern.sub(replacer, code)

        return new_code, changes