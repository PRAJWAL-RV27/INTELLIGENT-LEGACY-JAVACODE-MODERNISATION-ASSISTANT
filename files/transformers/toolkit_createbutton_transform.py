import re
from .base_transformer import BaseTransformer


class ToolkitCreateButtonTransformer(BaseTransformer):

    SAFE_METHODS = [
        "setLabel",
        "getLabel",
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

        assignment_pattern = re.compile(
            r'''
            ButtonPeer
            \s+
            (?P<peer>[A-Za-z_]\w*)
            \s*=\s*
            (?:Toolkit\.getDefaultToolkit\(\)|[A-Za-z_]\w*)
            \.createButton
            \(
            \s*(?P<button>[A-Za-z_]\w*)\s*
            \)
            \s*;
            ''',
            re.VERBOSE
        )

        # -----------------------------------------
        # Collect mappings
        # -----------------------------------------

        for m in assignment_pattern.finditer(content):
            peer_map[m.group("peer")] = m.group("button")

        # -----------------------------------------
        # Remove ButtonPeer assignments
        # -----------------------------------------

        if peer_map:
            content = assignment_pattern.sub("", content)
            changes.append(
                "Removed obsolete Toolkit.createButton() assignments."
            )

        # -----------------------------------------
        # Remove standalone createButton()
        # -----------------------------------------

        standalone = re.compile(
            r'''
            ^
            \s*
            (?:Toolkit\.getDefaultToolkit\(\)|[A-Za-z_]\w*)
            \.createButton
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
                "Removed standalone Toolkit.createButton() calls."
            )

        # -----------------------------------------
        # Rewrite only safe methods
        # -----------------------------------------

        methods = "|".join(self.SAFE_METHODS)

        for peer, button in peer_map.items():

            pattern = re.compile(
                rf'\b{re.escape(peer)}\.({methods})\s*\('
            )

            def repl(match):
                return f"{button}.{match.group(1)}("

            if pattern.search(content):
                changes.append(
                    f"Redirected ButtonPeer '{peer}' to Button '{button}'."
                )

            content = pattern.sub(repl, content)

                # -----------------------------------------
        # Step 5
        # Remove ButtonPeer import if no longer used
        # -----------------------------------------

        content = re.sub(
            r'^\s*import\s+java\.awt\.peer\.ButtonPeer\s*;\s*\n?',
            '',
            content,
            flags=re.MULTILINE
        )
        return content, changes