import re
from .base_transformer import BaseTransformer


class ToolkitCreateCheckboxTransformer(BaseTransformer):

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

        # Checkbox methods
        "setState",
        "getState",
        "setLabel",
        "getLabel",
        "setCheckboxGroup",
        "getCheckboxGroup",
    ]

    def transform(self, content: str):

        changes = []

        peer_map = {}

        # -----------------------------------------
        # Step 1
        # Collect CheckboxPeer -> Checkbox mappings
        # -----------------------------------------

        assignment_pattern = re.compile(
            r'''
            CheckboxPeer
            \s+
            (?P<peer>[A-Za-z_]\w*)
            \s*=\s*
            (?:Toolkit\.getDefaultToolkit\(\)|[A-Za-z_]\w*)
            \.createCheckbox
            \(
            \s*(?P<checkbox>[A-Za-z_]\w*)\s*
            \)
            \s*;
            ''',
            re.VERBOSE
        )

        for m in assignment_pattern.finditer(content):
            peer_map[m.group("peer")] = m.group("checkbox")

        # -----------------------------------------
        # Step 2
        # Remove CheckboxPeer assignments
        # -----------------------------------------

        if peer_map:
            content = assignment_pattern.sub("", content)
            changes.append(
                "Removed obsolete Toolkit.createCheckbox() assignments."
            )

        # -----------------------------------------
        # Step 3
        # Remove standalone createCheckbox()
        # -----------------------------------------

        standalone = re.compile(
            r'''
            ^
            \s*
            (?:Toolkit\.getDefaultToolkit\(\)|[A-Za-z_]\w*)
            \.createCheckbox
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
                "Removed standalone Toolkit.createCheckbox() calls."
            )

        # -----------------------------------------
        # Step 4
        # Rewrite peer.method() -> checkbox.method()
        # -----------------------------------------

        methods = "|".join(self.SAFE_METHODS)

        for peer, checkbox in peer_map.items():

            pattern = re.compile(
                rf'\b{re.escape(peer)}\.({methods})\s*\('
            )

            def repl(match):
                return f"{checkbox}.{match.group(1)}("

            if pattern.search(content):
                changes.append(
                    f"Redirected CheckboxPeer '{peer}' to Checkbox '{checkbox}'."
                )

            content = pattern.sub(repl, content)

        # -----------------------------------------
        # Step 5
        # Remove CheckboxPeer import if unused
        # -----------------------------------------

        remaining = re.sub(
            r'^\s*import\s+java\.awt\.peer\.CheckboxPeer\s*;\s*$',
            '',
            content,
            flags=re.MULTILINE
        )

        if re.search(r'\bCheckboxPeer\b', remaining) is None:
            content = remaining

        # -----------------------------------------
        # Step 6
        # Remove extra blank lines
        # -----------------------------------------

        content = re.sub(r'\n{3,}', '\n\n', content)

        return content, changes