import re
from .base_transformer import BaseTransformer


class DragSourceContextTransformer(BaseTransformer):
    """
    Replaces  obj.createDragSourceContext(...);  (statement form — ends with ';')
    with a startDrag() call.

    The peer transformer (DragSourceContextPeerTransformer) handles the
    expression form (used in assignments).  By splitting on the trailing ';'
    we avoid double-replacing the same call.
    """

    def transform(self, content: str):
        changes = []

        # Only match when the call is a standalone statement (ends with ';')
        pattern = r'(\b\w+\b)\.createDragSourceContext\s*\(([^)]*)\)\s*;'
        matches = list(re.finditer(pattern, content))

        for match in reversed(matches):
            obj = match.group(1)

            replacement = f"""
        // Auto-replaced deprecated createDragSourceContext()
        {obj}.startDrag(
            null,
            DragSource.DefaultCopyDrop,
            null,
            new DragSourceListener() {{
                public void dragDropEnd(DragSourceDropEvent dsde) {{}}
                public void dragEnter(DragSourceDragEvent dsde) {{}}
                public void dragExit(DragSourceEvent dse) {{}}
                public void dragOver(DragSourceDragEvent dsde) {{}}
                public void dropActionChanged(DragSourceDragEvent dsde) {{}}
            }}
        );
        """

            content = content[:match.start()] + replacement + content[match.end():]
            changes.append("Replaced createDragSourceContext() with startDrag() template")

        return content, changes