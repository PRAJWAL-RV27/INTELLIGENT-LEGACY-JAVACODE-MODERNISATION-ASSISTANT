import re
from .base_transformer import BaseTransformer


class ToolkitCreateChoiceTransformer(BaseTransformer):

    SAFE_METHODS = [
        # Component methods
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

        # Choice methods
        "add",
        "insert",
        "remove",
        "removeAll",
        "select",
        "getSelectedIndex",
        "getSelectedItem",
        "getSelectedObjects",
        "getItem",
        "getItemCount",
    ]

    def transform(self, content: str):

        changes = []

        peer_map = {}

        # -----------------------------------------
        # Step 1
        # Collect ChoicePeer -> Choice mappings
        # -----------------------------------------

        assignment_pattern = re.compile(
            r'''
            ChoicePeer
            \s+
            (?P<peer>[A-Za-z_]\w*)
            \s*=\s*
            (?:Toolkit\.getDefaultToolkit\(\)|[A-Za-z_]\w*)
            \.createChoice
            \(
            \s*(?P<choice>[A-Za-z_]\w*)\s*
            \)
            \s*;
            ''',
            re.VERBOSE
        )

        for m in assignment_pattern.finditer(content):
            peer_map[m.group("peer")] = m.group("choice")

        # -----------------------------------------
        # Step 2
        # Remove ChoicePeer assignments
        # -----------------------------------------

        if peer_map:
            content = assignment_pattern.sub("", content)
            changes.append(
                "Removed obsolete Toolkit.createChoice() assignments."
            )

        # -----------------------------------------
        # Step 3
        # Remove standalone createChoice()
        # -----------------------------------------

        standalone = re.compile(
            r'''
            ^
            \s*
            (?:Toolkit\.getDefaultToolkit\(\)|[A-Za-z_]\w*)
            \.createChoice
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
                "Removed standalone Toolkit.createChoice() calls."
            )

        # -----------------------------------------
        # Step 4
        # Rewrite peer.method() -> choice.method()
        # -----------------------------------------

        methods = "|".join(self.SAFE_METHODS)

        for peer, choice in peer_map.items():

            pattern = re.compile(
                rf'\b{re.escape(peer)}\.({methods})\s*\('
            )

            def repl(match):
                return f"{choice}.{match.group(1)}("

            if pattern.search(content):
                changes.append(
                    f"Redirected ChoicePeer '{peer}' to Choice '{choice}'."
                )

            content = pattern.sub(repl, content)

        # -----------------------------------------
        # Step 5
        # Remove ChoicePeer import if unused
        # -----------------------------------------

        remaining = re.sub(
            r'^\s*import\s+java\.awt\.peer\.ChoicePeer\s*;\s*$',
            '',
            content,
            flags=re.MULTILINE
        )

        if re.search(r'\bChoicePeer\b', remaining) is None:
            content = remaining

        # -----------------------------------------
        # Step 6
        # Remove extra blank lines
        # -----------------------------------------

        content = re.sub(r'\n{3,}', '\n\n', content)

        return content, changes