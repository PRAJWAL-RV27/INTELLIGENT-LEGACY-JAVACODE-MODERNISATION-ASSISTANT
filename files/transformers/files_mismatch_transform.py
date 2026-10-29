
import re


class FilesMismatchTransformer:
    NAME = "Files.readAllBytes + Arrays.equals -> Files.mismatch()"

    def transform(self, content: str):
        changes = []

        pattern = re.compile(
            r"java\.util\.Arrays\.equals\s*\(\s*"
            r"java\.nio\.file\.Files\.readAllBytes\s*\(\s*"
            r"(?P<p1>[A-Za-z_$]\w*)\s*\)\s*,\s*"
            r"java\.nio\.file\.Files\.readAllBytes\s*\(\s*"
            r"(?P<p2>[A-Za-z_$]\w*)\s*\)\s*\)"
            r"|Arrays\.equals\s*\(\s*"
            r"Files\.readAllBytes\s*\(\s*(?P<q1>[A-Za-z_$]\w*)\s*\)\s*,\s*"
            r"Files\.readAllBytes\s*\(\s*(?P<q2>[A-Za-z_$]\w*)\s*\)\s*\)"
        )

        def replace(match):
            p1 = match.group("p1") or match.group("q1")
            p2 = match.group("p2") or match.group("q2")

            changes.append(
                f"Replaced full-file byte-array comparison with Files.mismatch({p1}, {p2})"
            )

            return (
                f"java.nio.file.Files.mismatch({p1}, {p2}) == -1"
            )

        updated_content = pattern.sub(replace, content)
        return updated_content, changes
