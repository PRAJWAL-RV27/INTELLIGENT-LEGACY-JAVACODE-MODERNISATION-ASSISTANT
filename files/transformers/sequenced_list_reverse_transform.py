"""
sequenced_list_reverse_transform.py

Optional Java 21 optimization:

    List<T> reversed = new ArrayList<>(list);
    Collections.reverse(reversed);

becomes:

    List<T> reversed = list.reversed();

This avoids creating and reversing a complete copy.

The transformation is intentionally conservative:
- The destination variable must be declared as List.
- The source must also be a List.
- The source must not be modified later in the same file after
  the transformation point.

Why?

list.reversed() returns a VIEW, not an independent snapshot.
"""

from __future__ import annotations

import re


class SequencedListReverseTransformer:
    NAME = "List copy + Collections.reverse() -> List.reversed()"

    def transform(self, content: str):
        changes: list[str] = []

        pattern = re.compile(
            r"""
            (?P<type>
                List
                \s*
                <
                    [^;<>]+
                >
            )
            \s+
            (?P<target>[A-Za-z_$][\w$]*)
            \s*
            =
            \s*
            new
            \s+
            ArrayList
            \s*
            <
                \s*
            >
            \s*
            \(
            \s*
            (?P<source>[A-Za-z_$][\w$]*)
            \s*
            \)
            \s*
            ;
            \s*
            Collections
            \s*
            \.
            \s*
            reverse
            \s*
            \(
            \s*
            (?P=target)
            \s*
            \)
            \s*
            ;
            """,
            re.VERBOSE | re.MULTILINE,
        )

        def replace(match):
            target = match.group("target")
            source = match.group("source")
            declared_type = match.group("type")

            # ----------------------------------------------------------
            # The source must really be a List. For a Set / Deque the code
            # `List<T> x = set.reversed();` does not compile (reversed() of a
            # LinkedHashSet is a SequencedSet, not a List).
            # ----------------------------------------------------------
            decl_types = {
                m.group(1)
                for m in re.finditer(
                    r"(?<![\w$.])([A-Za-z_$][\w$]*)(?:\s*<[^;(){}=]*?>)?\s+"
                    + re.escape(source)
                    + r"\s*(?:=|;|,|\)|:)",
                    content[: match.start()],
                )
                if m.group(1) not in {"return", "else", "new", "throw", "case"}
            }
            if not decl_types or not decl_types <= {
                "List", "ArrayList", "LinkedList", "Vector"
            }:
                return match.group(0)

            # ----------------------------------------------------------
            # Conservative safety check:
            #
            # If the source list is modified later, the old code had
            # snapshot semantics while reversed() has view semantics.
            # ----------------------------------------------------------

            end_position = match.end()
            remaining = content[end_position:]

            mutation_pattern = re.compile(
                rf"""
                \b{re.escape(source)}
                \s*
                \.
                \s*
                (?:
                    add
                    |addAll
                    |remove
                    |removeAll
                    |retainAll
                    |clear
                    |set
                    |sort
                )
                \s*\(
                """,
                re.VERBOSE,
            )

            if mutation_pattern.search(remaining):
                return match.group(0)

            changes.append(
                f"Replaced reverse copy of '{source}' "
                f"with Java 21 {source}.reversed()"
            )

            return (
                f"{declared_type} {target} = "
                f"{source}.reversed();"
            )

        transformed = pattern.sub(replace, content)

        return transformed, changes
