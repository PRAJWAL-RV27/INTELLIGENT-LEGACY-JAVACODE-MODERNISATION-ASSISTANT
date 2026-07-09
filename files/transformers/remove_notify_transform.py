import re
from .base_transformer import BaseTransformer


class RemoveNotifyTransformer(BaseTransformer):
    def transform(self, content: str):
        changes = []

        class_pattern = r'class\s+\w+[^{]*\{'
        # removeNotify with NO parameters (no-arg override)
        method_header = r'\b(public|protected)\s+void\s+removeNotify\s*\(\s*\)\s*\{'

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

            # Remove entire method
            content = content[:method_match.start()] + content[method_end:]

            if cleaned_body == "":
                changes.append("Removed redundant removeNotify() (only super call)")
                continue

            # Re-locate class insert position after mutation
            class_match = re.search(class_pattern, content)
            if not class_match:
                continue
            insert_pos = class_match.end()

            new_method = f"""

    // Auto-migrated from removeNotify()
    public void cleanupResources() {{

        // Preserved cleanup logic
        {cleaned_body}
    }}
"""
            content = content[:insert_pos] + new_method + content[insert_pos:]
            changes.append("Converted removeNotify() to cleanupResources()")

        return content, changes