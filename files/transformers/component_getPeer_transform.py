"""
component_getpeer_transform.py

Migrates common usages of Component.getPeer()
to modern AWT APIs.

Skips MenuComponent.getPeer(), which is handled by
MenuComponentGetPeerTransformer.
"""

import re
from .base_transformer import BaseTransformer


class ComponentGetPeerTransformer(BaseTransformer):

    def transform(self, content: str):

        changes = []

        lines = content.splitlines()
        new_lines = []

        # ----------------------------------------------------
        # Collect all variables of type MenuComponent
        # Handles:
        # MenuComponent menu;
        # MenuComponent menu = ...
        # void test(MenuComponent menu)
        # foo(Component c, MenuComponent menu)
        # ----------------------------------------------------
        menu_component_vars = set()

        declaration_pattern = re.compile(
            r'\bMenuComponent\s+([A-Za-z_][A-Za-z0-9_]*)'
        )

        parameter_pattern = re.compile(
            r'[,(]\s*MenuComponent\s+([A-Za-z_][A-Za-z0-9_]*)'
        )

        for line in lines:

            # Local variable declarations
            for match in declaration_pattern.finditer(line):
                menu_component_vars.add(match.group(1))

            # Method parameters
            for match in parameter_pattern.finditer(line):
                menu_component_vars.add(match.group(1))

        # ----------------------------------------------------
        # Process file
        # ----------------------------------------------------
        for line in lines:

            new_line = line

            # Skip MenuComponent.getPeer()
            skip = False

            for var in menu_component_vars:
                if f"{var}.getPeer()" in new_line:
                    skip = True
                    break

            if skip:
                new_lines.append(new_line)
                continue

            # ------------------------------------------------
            # Case 1:
            # component.getPeer() != null
            # ->
            # component.isDisplayable()
            # ------------------------------------------------
            if ".getPeer() != null" in new_line:
                new_line = new_line.replace(
                    ".getPeer() != null",
                    ".isDisplayable()"
                )
                changes.append(
                    "Replaced getPeer() != null with isDisplayable()."
                )

            # ------------------------------------------------
            # Case 2:
            # component.getPeer() == null
            # ->
            # !component.isDisplayable()
            # ------------------------------------------------
            if ".getPeer() == null" in new_line:
                new_line = new_line.replace(
                    ".getPeer() == null",
                    ".isDisplayable() == false"
                )
                changes.append(
                    "Replaced getPeer() == null with !isDisplayable()."
                )

            # ------------------------------------------------
            # Case 3:
            # component.getPeer();
            # ->
            # component.addNotify();
            # ------------------------------------------------
            stripped = new_line.strip()

            if (
                stripped.endswith(".getPeer();")
                and "=" not in stripped
                and "return" not in stripped
                and "if" not in stripped
                and "while" not in stripped
            ):
                new_line = new_line.replace(
                    ".getPeer();",
                    ".addNotify();"
                )
                changes.append(
                    "Replaced getPeer() call with addNotify()."
                )

            new_lines.append(new_line)

        return "\n".join(new_lines), changes