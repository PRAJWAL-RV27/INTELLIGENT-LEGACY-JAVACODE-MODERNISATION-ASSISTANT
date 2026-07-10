import re
from .base_transformer import BaseTransformer


class MenuComponentGetPeerTransformer(BaseTransformer):
    """
    Migrates MenuComponent.getPeer() usages.

    Transformations:
    1. menu.getPeer() == null  -> menu.getParent() == null
    2. menu.getPeer() != null  -> menu.getParent() != null
    3. menu.getPeer()          -> null
    """

    def transform(self, content: str):
        changes = []

        if "getPeer()" not in content:
            return content, changes

        # ---------------------------------------------------------
        # Case 1: menu.getPeer() == null
        # ---------------------------------------------------------
        pattern = re.compile(r'(\b\w+\b)\.getPeer\(\)\s*==\s*null')
        matches = pattern.findall(content)
        if matches:
            content = pattern.sub(r'\1.getParent() == null', content)
            changes.append(
                "Replaced MenuComponent.getPeer() == null with getParent() == null"
            )

        # ---------------------------------------------------------
        # Case 2: menu.getPeer() != null
        # ---------------------------------------------------------
        pattern = re.compile(r'(\b\w+\b)\.getPeer\(\)\s*!=\s*null')
        matches = pattern.findall(content)
        if matches:
            content = pattern.sub(r'\1.getParent() != null', content)
            changes.append(
                "Replaced MenuComponent.getPeer() != null with getParent() != null"
            )

        # ---------------------------------------------------------
        # Case 3: Any remaining getPeer()
        # ---------------------------------------------------------
        pattern = re.compile(r'(\b\w+\b)\.getPeer\(\)')
        matches = pattern.findall(content)
        if matches:
            content = pattern.sub("null", content)
            changes.append(
                "Replaced remaining MenuComponent.getPeer() usages with null"
            )

        return content, changes