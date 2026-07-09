import re
from .base_transformer import BaseTransformer


class DragSourceContextPeerTransformer(BaseTransformer):
    """
    Handles  createDragSourceContext(...)  in the EXPRESSION/ASSIGNMENT form
    (i.e. the result is used in an assignment or returned).

    The statement form (standalone call ending in ';') is handled by
    DragSourceContextTransformer, so we only match when there is NO
    trailing ';' immediately after the closing parenthesis.
    """

    def transform(self, content: str):
        changes = []

        # Match expression form: does NOT end with ';' on the same token
        # We require the match to NOT be followed by optional-whitespace + ';'
        pattern = re.compile(
            r'(\b\w+\b)\.createDragSourceContext\s*\(([^)]*)\)(?!\s*;)'
        )

        matches = list(pattern.finditer(content))

        for match in reversed(matches):
            obj = match.group(1)
            before = content[:match.start()]
            # Check if the expression is on the right-hand side of an assignment
            is_assigned = re.search(r'=\s*$', before.strip().split('\n')[-1])

            if not is_assigned:
                replacement = f"""
        // Auto-replaced removed API: createDragSourceContext(...)
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
        )
        """
                changes.append("Replaced createDragSourceContext() with startDrag()")
            else:
                replacement = """
        // WARNING: Removed API createDragSourceContext() used in assignment
        // Returning null to preserve compilation — manual fix required
        null
        """
                changes.append("Replaced createDragSourceContext() with null (assignment case)")

            content = content[:match.start()] + replacement + content[match.end():]

        return content, changes