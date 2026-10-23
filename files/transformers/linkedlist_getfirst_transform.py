"""
linkedlist_getfirst_transform.py

Optional Java 21 modernization:

    LinkedList.get(0)
        ->
    LinkedList.getFirst()

The transformation is intentionally conservative.

It is only applied when:
1. The variable is declared as LinkedList.
2. The get(0) operation occurs inside a block where the same list
   has an explicit size()/isEmpty() check proving that it is non-empty.

Why the safety check?

For an empty list:

    list.get(0)

throws IndexOutOfBoundsException, while:

    list.getFirst()

throws NoSuchElementException.

Therefore blindly replacing get(0) would not preserve semantics.
"""

from __future__ import annotations

import re


class LinkedListGetFirstTransformer:
    """
    Optional Java 21 transformation:

        LinkedList.get(0) -> LinkedList.getFirst()

    only when a preceding non-empty condition is detected.
    """

    NAME = "LinkedList.get(0) -> getFirst()"

    def transform(self, content: str):
        changes: list[str] = []

        # --------------------------------------------------------------
        # Find LinkedList variable declarations.
        #
        # Examples:
        #
        # LinkedList<Integer> list = new LinkedList<>();
        # LinkedList<String> values = new LinkedList<String>();
        # --------------------------------------------------------------

        declaration_pattern = re.compile(
            r"""
            \b
            LinkedList
            \s*
            <
                [^;<>]+
            >
            \s+
            (?P<variable>[A-Za-z_$][\w$]*)
            \s*
            =
            \s*
            new
            \s+
            LinkedList
            """,
            re.VERBOSE,
        )

        variables = {
            match.group("variable")
            for match in declaration_pattern.finditer(content)
        }

        if not variables:
            return content, changes

        transformed = content

        # --------------------------------------------------------------
        # Process each LinkedList variable.
        # --------------------------------------------------------------

        for variable in variables:

            # ----------------------------------------------------------
            # Safe condition:
            #
            # if (!list.isEmpty()) {
            #     list.get(0);
            # }
            #
            # OR:
            #
            # if (list.size() > 0) {
            #     list.get(0);
            # }
            #
            # OR:
            #
            # if (list.size() != 0) {
            #     list.get(0);
            # }
            #
            # ----------------------------------------------------------

            safe_patterns = [
                re.compile(
                    rf"""
                    (?P<prefix>
                        if
                        \s*
                        \(
                        \s*
                        !
                        \s*
                        {re.escape(variable)}
                        \s*
                        \.
                        \s*
                        isEmpty
                        \s*
                        \(
                        \s*
                        \)
                        \s*
                        \)
                        \s*
                        \{{ 
                    )
                    (?P<body>
                        [^{{}}]*
                    )
                    (?P<suffix>\}})
                    """,
                    re.VERBOSE | re.DOTALL,
                ),

                re.compile(
                    rf"""
                    (?P<prefix>
                        if
                        \s*
                        \(
                        \s*
                        {re.escape(variable)}
                        \s*
                        \.
                        \s*
                        size
                        \s*
                        \(
                        \s*
                        \)
                        \s*
                        >
                        \s*
                        0
                        \s*
                        \)
                        \s*
                        \{{ 
                    )
                    (?P<body>
                        [^{{}}]*
                    )
                    (?P<suffix>\}})
                    """,
                    re.VERBOSE | re.DOTALL,
                ),

                re.compile(
                    rf"""
                    (?P<prefix>
                        if
                        \s*
                        \(
                        \s*
                        {re.escape(variable)}
                        \s*
                        \.
                        \s*
                        size
                        \s*
                        \(
                        \s*
                        \)
                        \s*
                        !=
                        \s*
                        0
                        \s*
                        \)
                        \s*
                        \{{ 
                    )
                    (?P<body>
                        [^{{}}]*
                    )
                    (?P<suffix>\}})
                    """,
                    re.VERBOSE | re.DOTALL,
                ),
            ]

            for pattern in safe_patterns:

                def replace_safe_block(match):
                    body = match.group("body")

                    get_pattern = re.compile(
                        rf"""
                        \b
                        {re.escape(variable)}
                        \s*
                        \.
                        \s*
                        get
                        \s*
                        \(
                        \s*
                        0
                        \s*
                        \)
                        """,
                        re.VERBOSE,
                    )

                    new_body, count = get_pattern.subn(
                        f"{variable}.getFirst()",
                        body,
                    )

                    if count:
                        changes.append(
                            f"{self.NAME} for variable '{variable}'"
                        )

                    return (
                        match.group("prefix")
                        + new_body
                        + match.group("suffix")
                    )

                transformed = pattern.sub(
                    replace_safe_block,
                    transformed,
                )

        return transformed, changes