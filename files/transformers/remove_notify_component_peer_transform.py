import re
from .base_transformer import BaseTransformer


class RemoveNotifyComponentPeerTransformer(BaseTransformer):
    def transform(self, content: str):
        changes = []

        class_pattern = r'class\s+\w+[^{]*\{'
        method_header = r'\b(public|protected)\s+void\s+removeNotify\s*\(\s*ComponentPeer\s+\w+\s*\)\s*\{'

        while True:
            method_match = re.search(method_header, content)
            if not method_match:
                break

            # Balanced-brace extraction
            brace_start = content.index('{', method_match.start())
            depth, i = 0, brace_start
            while i < len(content):
                if content[i] == '{':
                    depth += 1
                elif content[i] == '}':
                    depth -= 1
                    if depth == 0:
                        break
                i += 1
            method_end = i + 1
            original_body = content[brace_start + 1:i]

            # Remove super call from body
            cleaned_body = re.sub(
                r'super\.removeNotify\s*\(\s*\)\s*;', '', original_body
            ).strip()

            # Remove original method
            content = content[:method_match.start()] + content[method_end:]

            if cleaned_body == "":
                changes.append("Removed empty removeNotify(ComponentPeer)")
                continue

            # Re-locate class insert position after mutation
            class_match = re.search(class_pattern, content)
            if not class_match:
                continue
            insert_pos = class_match.end()

            new_method = f"""

    // Auto-migrated from removeNotify(ComponentPeer)
    public void cleanupResources() {{

        // Preserved cleanup logic
        {cleaned_body}
    }}
"""
            content = content[:insert_pos] + new_method + content[insert_pos:]
            changes.append("Converted removeNotify(ComponentPeer) to cleanupResources()")

        # ---------- HANDLE DIRECT CALLS ----------
        # Matches: obj.removeNotify(anyArgs);
        call_pattern = r'\b(\w+)\.removeNotify\s*\([^)]*\)\s*;'
        for match in reversed(list(re.finditer(call_pattern, content))):
            replacement = (
                "\n        // Removed deprecated removeNotify(ComponentPeer) call"
                "\n        // Use cleanupResources() if required\n        "
            )
            content = content[:match.start()] + replacement + content[match.end():]
            changes.append("Removed removeNotify(ComponentPeer) call")

        return content, changes