"""
sequenced_key_set_transform.py

Optional Java 21 optimization:

    List<K> keys = new ArrayList<>(map.keySet());

becomes:

    SequencedSet<K> keys = map.sequencedKeySet();

This avoids creating a complete copy of the keys.
"""

from __future__ import annotations

import re


class SequencedKeySetTransformer:
    NAME = "LinkedHashMap.keySet() copy -> sequencedKeySet()"

    def transform(self, content: str):
        changes: list[str] = []

        pattern = re.compile(
            r"""
            (?P<type>
                List
                \s*
                <
                    (?P<generic>[^;<>]+)
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
            (?P<map>[A-Za-z_$][\w$]*)
            \s*
            \.
            \s*
            keySet
            \s*
            \(
            \s*
            \)
            \s*
            \)
            \s*
            ;
            """,
            re.VERBOSE | re.MULTILINE,
        )

        def replace(match):
            generic = match.group("generic").strip()
            target = match.group("target")
            map_name = match.group("map")

            end_position = match.end()
            remaining = content[end_position:]

            mutation_pattern = re.compile(
                rf"""
                \b{re.escape(map_name)}
                \s*
                \.
                \s*
                (?:
                    put
                    |putAll
                    |remove
                    |clear
                    |replace
                    |replaceAll
                    |compute
                    |computeIfAbsent
                    |computeIfPresent
                )
                \s*\(
                """,
                re.VERBOSE,
            )

            if mutation_pattern.search(remaining):
                return match.group(0)

            changes.append(
                f"Replaced copied keys of '{map_name}' "
                f"with Java 21 {map_name}.sequencedKeySet()"
            )

            return (
                f"SequencedSet<{generic}> "
                f"{target} = {map_name}.sequencedKeySet();"
            )

        transformed = pattern.sub(replace, content)

        if changes:
            from .base_transformer import add_import
            transformed = add_import(transformed, "java.util.SequencedSet")

        return transformed, changes
