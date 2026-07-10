"""
component_getpeer_transform.py

Migrates common usages of Component.getPeer()
to modern AWT APIs.
"""

from .base_transformer import BaseTransformer


class ComponentGetPeerTransformer(BaseTransformer):

    def transform(self, content: str):

        changes = []

        lines = content.splitlines()
        new_lines = []

        for line in lines:

            new_line = line

            # Case 1:
            # if(component.getPeer() != null)
            if ".getPeer() != null" in new_line:
                new_line = new_line.replace(
                    ".getPeer() != null",
                    ".isDisplayable()"
                )
                changes.append(
                    "Replaced getPeer() != null with isDisplayable()."
                )

            # Case 2:
            # if(component.getPeer() == null)
            if ".getPeer() == null" in new_line:
                new_line = new_line.replace(
                    ".getPeer() == null",
                    ".isDisplayable() == false"
                )
                changes.append(
                    "Replaced getPeer() == null with !isDisplayable()."
                )

            # Case 3:
            # component.getPeer();
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