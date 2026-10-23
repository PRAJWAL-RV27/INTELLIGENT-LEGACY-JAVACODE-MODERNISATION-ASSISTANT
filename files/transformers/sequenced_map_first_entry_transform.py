
"""
sequenced_map_first_entry_transform.py

Optional Java 21 optimization:

    map.entrySet().iterator().next()

becomes:

    map.firstEntry()

Java 21 introduced firstEntry() through SequencedMap.

This transformation is intentionally conservative.

It only transforms variables that are declared as LinkedHashMap,
because LinkedHashMap has a defined encounter order.

The transformation also avoids changing code where the map is
modified later in the source file.

The performance-aware optimizer decides whether the candidate
should actually be kept.
"""

from __future__ import annotations

import re


class SequencedMapFirstEntryTransformer:

    NAME = (
        "Map.entrySet().iterator().next() "
        "-> Map.firstEntry()"
    )

    def transform(self, content: str):

        changes: list[str] = []

        # ----------------------------------------------------------
        # Find LinkedHashMap declarations.
        #
        # Example:
        #
        # LinkedHashMap<String, Integer> map =
        #         new LinkedHashMap<>();
        # ----------------------------------------------------------

        declaration_pattern = re.compile(
            r"""
            \b
            LinkedHashMap
            \s*
            <
                [^<>;]+
            >
            \s+
            (?P<variable>
                [A-Za-z_$][\w$]*
            )
            \s*
            =
            \s*
            new
            \s+
            LinkedHashMap
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

        for variable in variables:

            # ------------------------------------------------------
            # Match:
            #
            # map.entrySet().iterator().next()
            #
            # Allow whitespace/newlines between calls.
            # ------------------------------------------------------

            pattern = re.compile(
                rf"""
                \b
                {re.escape(variable)}
                \s*
                \.
                \s*
                entrySet
                \s*
                \(
                \s*
                \)
                \s*
                \.
                \s*
                iterator
                \s*
                \(
                \s*
                \)
                \s*
                \.
                \s*
                next
                \s*
                \(
                \s*
                \)
                """,
                re.VERBOSE,
            )

            matches = list(pattern.finditer(transformed))

            if not matches:
                continue

            # ------------------------------------------------------
            # Safety check:
            #
            # firstEntry() returns a view-backed Map.Entry.
            #
            # Do not transform if the map is modified later.
            # ------------------------------------------------------

            for match in reversed(matches):

                remaining = transformed[match.end():]

                mutation_pattern = re.compile(
                    rf"""
                    \b
                    {re.escape(variable)}
                    \s*
                    \.
                    \s*
                    (?:
                        put
                        |putIfAbsent
                        |putAll
                        |remove
                        |removeAll
                        |clear
                        |replace
                        |replaceAll
                        |compute
                        |computeIfAbsent
                        |computeIfPresent
                        |merge
                    )
                    \s*
                    \(
                    """,
                    re.VERBOSE,
                )

                if mutation_pattern.search(remaining):
                    continue

                start = match.start()
                end = match.end()

                transformed = (
                    transformed[:start]
                    + f"{variable}.firstEntry()"
                    + transformed[end:]
                )

                changes.append(
                    f"Replaced "
                    f"{variable}.entrySet().iterator().next() "
                    f"with {variable}.firstEntry()"
                )

        return transformed, changes

