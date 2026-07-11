import re
from .base_transformer import BaseTransformer


class ToolkitCreateCanvasTransformer(BaseTransformer):

    SAFE_METHODS = [
        "setEnabled",
        "isEnabled",
        "setVisible",
        "isVisible",
        "setBackground",
        "getBackground",
        "setForeground",
        "getForeground",
        "setFont",
        "getFont",
        "setCursor",
        "setBounds",
        "setSize",
        "setLocation",
        "setName",
        "getName",
        "requestFocus",
        "repaint",
        "invalidate",
        "validate",
        "setFocusable",
        "isFocusable",
    ]

    def transform(self, content: str):

        changes = []

        peer_map = {}

        # -----------------------------------------
        # Step 1
        # Collect CanvasPeer -> Canvas mappings
        # -----------------------------------------

        assignment_pattern = re.compile(
            r'''
            CanvasPeer
            \s+
            (?P<peer>[A-Za-z_]\w*)
            \s*=\s*
            (?:Toolkit\.getDefaultToolkit\(\)|[A-Za-z_]\w*)
            \.createCanvas
            \(
            \s*(?P<canvas>[A-Za-z_]\w*)\s*
            \)
            \s*;
            ''',
            re.VERBOSE
        )

        for m in assignment_pattern.finditer(content):
            peer_map[m.group("peer")] = m.group("canvas")

        # -----------------------------------------
        # Step 2
        # Remove CanvasPeer assignments
        # -----------------------------------------

        if peer_map:
            content = assignment_pattern.sub("", content)
            changes.append(
                "Removed obsolete Toolkit.createCanvas() assignments."
            )

        # -----------------------------------------
        # Step 3
        # Remove standalone createCanvas()
        # -----------------------------------------

        standalone = re.compile(
            r'''
            ^
            \s*
            (?:Toolkit\.getDefaultToolkit\(\)|[A-Za-z_]\w*)
            \.createCanvas
            \(
            \s*[A-Za-z_]\w*\s*
            \)
            \s*;
            \s*$
            ''',
            re.MULTILINE | re.VERBOSE
        )

        if standalone.search(content):
            content = standalone.sub("", content)
            changes.append(
                "Removed standalone Toolkit.createCanvas() calls."
            )

        # -----------------------------------------
        # Step 4
        # Rewrite peer.method() -> canvas.method()
        # -----------------------------------------

        methods = "|".join(self.SAFE_METHODS)

        for peer, canvas in peer_map.items():

            pattern = re.compile(
                rf'\b{re.escape(peer)}\.({methods})\s*\('
            )

            def repl(match):
                return f"{canvas}.{match.group(1)}("

            if pattern.search(content):
                changes.append(
                    f"Redirected CanvasPeer '{peer}' to Canvas '{canvas}'."
                )

            content = pattern.sub(repl, content)

        # -----------------------------------------
        # Step 5
        # Remove CanvasPeer import if unused
        # -----------------------------------------

        remaining = re.sub(
            r'^\s*import\s+java\.awt\.peer\.CanvasPeer\s*;\s*$',
            '',
            content,
            flags=re.MULTILINE
        )

        if re.search(r'\bCanvasPeer\b', remaining) is None:
            content = remaining

        # -----------------------------------------
        # Step 6
        # Remove extra blank lines
        # -----------------------------------------

        content = re.sub(r'\n{3,}', '\n\n', content)

        return content, changes