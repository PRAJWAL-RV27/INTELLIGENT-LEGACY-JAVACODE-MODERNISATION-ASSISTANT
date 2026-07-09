import re
from .base_transformer import BaseTransformer

class AddNotifyTransformer(BaseTransformer):
    def transform(self, content: str):
        changes = []

        # ---------- ADD IMPORTS SAFELY ----------
        if "import java.awt.dnd" not in content:
            content = "import java.awt.dnd.*;\nimport java.awt.*;\n" + content
            changes.append("Added AWT DnD imports")

        # ---------- FIND CLASS ----------
        class_pattern = r'class\s+\w+[^{]*\{'
        class_match = re.search(class_pattern, content)

        if not class_match:
            return content, changes  # no class found

        insert_pos = class_match.end()

        # ---------- HANDLE addNotify METHOD ----------
        method_pattern = r'(public|protected)\s+void\s+addNotify\s*\(\s*DropTargetContextPeer\s+\w+\s*\)\s*\{([\s\S]*?)\}'
        method_matches = list(re.finditer(method_pattern, content))

        for match in reversed(method_matches):
            method_body = match.group(2).strip()

            # Remove old method
            content = content[:match.start()] + content[match.end():]

            if method_body == "":
                changes.append("Removed empty addNotify()")
                continue

            # ✅ SAFE METHOD (NO 'this', always works)
            new_method = f"""

    // Auto-migrated from addNotify(DropTargetContextPeer)
    public void setupDropTarget(java.awt.Component component) {{

        DropTarget dt = new DropTarget(component, new DropTargetListener() {{

            public void dragEnter(DropTargetDragEvent dtde) {{}}

            public void dragOver(DropTargetDragEvent dtde) {{}}

            public void dropActionChanged(DropTargetDragEvent dtde) {{}}

            public void dragExit(DropTargetEvent dte) {{}}

            public void drop(DropTargetDropEvent dtde) {{
                // Preserved logic from addNotify
                {method_body}
            }}
        }});
    }}
"""

            content = content[:insert_pos] + new_method + content[insert_pos:]
            changes.append("Replaced addNotify() with setupDropTarget(Component)")

        # ---------- HANDLE DIRECT CALLS ----------
        call_pattern = r'(\b\w+\b)\.addNotify\s*\(([\s\S]*?)\)\s*;'
        call_matches = list(re.finditer(call_pattern, content))

        for match in reversed(call_matches):
            full_match = match.group(0)

            replacement = """
        // Removed deprecated addNotify() call
        // Call setupDropTarget(component) instead if needed
        """

            content = content[:match.start()] + replacement + content[match.end():]
            changes.append("Removed addNotify() call")

        return content, changes