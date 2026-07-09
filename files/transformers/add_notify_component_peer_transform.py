import re
from .base_transformer import BaseTransformer

class AddNotifyComponentPeerTransformer(BaseTransformer):
    def transform(self, content: str):
        changes = []

        # ---------- FIND CLASS ----------
        class_pattern = r'class\s+\w+[^{]*\{'
        class_matches = list(re.finditer(class_pattern, content))

        if not class_matches:
            return content, changes

        # ---------- FIND METHOD ----------
        method_pattern = r'\b(public|protected)\s+void\s+addNotify\s*\(\s*ComponentPeer\s+\w+\s*\)\s*\{([\s\S]*?)\}'
        method_matches = list(re.finditer(method_pattern, content))

        for match in reversed(method_matches):
            original_body = match.group(2)

            # Remove super call
            cleaned_body = re.sub(
                r'super\.addNotify\s*\(\s*\)\s*;', '', original_body
            ).strip()

            # Remove original method
            content = content[:match.start()] + content[match.end():]

            # ---------- CASE 1: EMPTY ----------
            if cleaned_body == "":
                changes.append("Removed empty addNotify(ComponentPeer)")
                continue

            # ---------- FIND CLASS POSITION ----------
            insert_pos = None
            for cls in reversed(class_matches):
                if cls.start() < match.start():
                    insert_pos = cls.end()
                    break

            if insert_pos is None:
                continue

            # ---------- CREATE NEW METHOD ----------
            new_method = f"""

    // Auto-migrated from addNotify(ComponentPeer)
    public void initializeComponent() {{

        // Preserved initialization logic
        {cleaned_body}
    }}
"""

            content = content[:insert_pos] + new_method + content[insert_pos:]
            changes.append("Converted addNotify(ComponentPeer) to initializeComponent()")

        # ---------- HANDLE DIRECT CALLS ----------
        call_pattern = r'(\b\w+\b)\.addNotify\s*\(([\s\S]*?)\)\s*;'
        call_matches = list(re.finditer(call_pattern, content))

        for match in reversed(call_matches):
            full_match = match.group(0)

            replacement = """
        // Removed deprecated addNotify(ComponentPeer) call
        // Use explicit initialization instead if required
        """

            content = content[:match.start()] + replacement + content[match.end():]
            changes.append("Removed addNotify(ComponentPeer) call")

        return content, changes