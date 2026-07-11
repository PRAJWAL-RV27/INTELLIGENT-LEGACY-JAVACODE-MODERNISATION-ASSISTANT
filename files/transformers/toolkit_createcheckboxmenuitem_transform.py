import re
from .base_transformer import BaseTransformer


class ToolkitCreateCheckboxMenuItemTransformer(BaseTransformer):

    SAFE_METHODS = [
        # MenuItem methods
        "setLabel",
        "getLabel",
        "setEnabled",
        "isEnabled",
        "setShortcut",
        "getShortcut",

        # CheckboxMenuItem methods
        "setState",
        "getState",
    ]

    def transform(self, content: str):

        changes = []

        peer_map = {}

        # -----------------------------------------
        # Step 1
        # Collect CheckboxMenuItemPeer -> CheckboxMenuItem mappings
        # -----------------------------------------

        assignment_pattern = re.compile(
            r'''
            CheckboxMenuItemPeer
            \s+
            (?P<peer>[A-Za-z_]\w*)
            \s*=\s*
            (?:Toolkit\.getDefaultToolkit\(\)|[A-Za-z_]\w*)
            \.createCheckboxMenuItem
            \(
            \s*(?P<item>[A-Za-z_]\w*)\s*
            \)
            \s*;
            ''',
            re.VERBOSE
        )

        for m in assignment_pattern.finditer(content):
            peer_map[m.group("peer")] = m.group("item")

        # -----------------------------------------
        # Step 2
        # Remove CheckboxMenuItemPeer assignments
        # -----------------------------------------

        if peer_map:
            content = assignment_pattern.sub("", content)
            changes.append(
                "Removed obsolete Toolkit.createCheckboxMenuItem() assignments."
            )

        # -----------------------------------------
        # Step 3
        # Remove standalone createCheckboxMenuItem()
        # -----------------------------------------

        standalone = re.compile(
            r'''
            ^
            \s*
            (?:Toolkit\.getDefaultToolkit\(\)|[A-Za-z_]\w*)
            \.createCheckboxMenuItem
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
                "Removed standalone Toolkit.createCheckboxMenuItem() calls."
            )

        # -----------------------------------------
        # Step 4
        # Rewrite peer.method() -> checkboxMenuItem.method()
        # -----------------------------------------

        methods = "|".join(self.SAFE_METHODS)

        for peer, item in peer_map.items():

            pattern = re.compile(
                rf'\b{re.escape(peer)}\.({methods})\s*\('
            )

            def repl(match):
                return f"{item}.{match.group(1)}("

            if pattern.search(content):
                changes.append(
                    f"Redirected CheckboxMenuItemPeer '{peer}' to CheckboxMenuItem '{item}'."
                )

            content = pattern.sub(repl, content)

        # -----------------------------------------
        # Step 5
        # Remove CheckboxMenuItemPeer import if unused
        # -----------------------------------------

        remaining = re.sub(
            r'^\s*import\s+java\.awt\.peer\.CheckboxMenuItemPeer\s*;\s*$',
            '',
            content,
            flags=re.MULTILINE
        )

        if re.search(r'\bCheckboxMenuItemPeer\b', remaining) is None:
            content = remaining

        # -----------------------------------------
        # Step 6
        # Remove extra blank lines
        # -----------------------------------------

        content = re.sub(r'\n{3,}', '\n\n', content)

        return content, changes