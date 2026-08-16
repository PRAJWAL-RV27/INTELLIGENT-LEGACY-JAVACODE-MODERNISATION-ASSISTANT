import re

from .base_transformer import BaseTransformer


class JavaxActivityManualReviewTransformer(BaseTransformer):
    """Report javax.activity references without modifying Java source."""

    OLD_PACKAGE = "javax.activity"
    REPORT_REASON = "javax.activity API was removed from the JDK"

    def transform(self, content: str) -> tuple[str, list[str]]:
        matches = self._extract_code_references(content)
        if not matches:
            return content, []

        report_entries = []
        for api in sorted(matches):
            if api == self.OLD_PACKAGE:
                api = f"{self.OLD_PACKAGE}.*"
            report_entries.append(
                f"Original API: {api}; Replacement API: None; "
                f"Reason: {self.REPORT_REASON}; Action: MANUAL_REVIEW"
            )
        return content, report_entries

    def _extract_code_references(self, content: str) -> set[str]:
        matches: set[str] = set()
        i = 0
        while i < len(content):
            special = self._next_special_index(content, i)
            if special is None:
                self._collect_matches_from_code(content[i:], matches)
                break

            if special > i:
                self._collect_matches_from_code(content[i:special], matches)
            token = self._read_special_token(content, special)
            if token is None:
                i = special + 1
                continue
            i = special + len(token)

        return matches

    def _collect_matches_from_code(self, segment: str, matches: set[str]) -> None:
        pattern = re.compile(r"(?<![A-Za-z0-9_])javax\.activity(?:\.(?:\*|[A-Za-z_][A-Za-z0-9_]*))?(?![A-Za-z0-9_])")
        for match in pattern.finditer(segment):
            value = match.group(0)
            if value.endswith(".*"):
                matches.add("javax.activity.*")
            elif value.startswith("javax.activity."):
                matches.add(value)
            elif value == "javax.activity":
                matches.add("javax.activity.*")

    def _next_special_index(self, content: str, start: int) -> int | None:
        markers = [
            content.find("//", start),
            content.find("/*", start),
            content.find('"""', start),
            content.find('"', start),
            content.find("'", start),
        ]
        valid = [idx for idx in markers if idx != -1]
        if not valid:
            return None
        return min(valid)

    def _read_special_token(self, content: str, start: int) -> str | None:
        if content.startswith("//", start):
            end = content.find("\n", start)
            return content[start:] if end == -1 else content[start:end]

        if content.startswith("/*", start):
            end = content.find("*/", start + 2)
            if end == -1:
                return content[start:]
            return content[start:end + 2]

        if content.startswith('"""', start):
            end = self._find_text_block_end(content, start + 3)
            return content[start:end]

        if content[start] == '"':
            end = self._find_string_end(content, start + 1)
            return content[start:end]

        if content[start] == "'":
            end = self._find_char_end(content, start + 1)
            return content[start:end]

        return None

    def _find_text_block_end(self, content: str, start: int) -> int:
        i = start
        while i < len(content):
            if content.startswith('"""', i):
                return i + 3
            i += 1
        return len(content)

    def _find_string_end(self, content: str, start: int) -> int:
        i = start
        while i < len(content):
            if content[i] == '\\':
                i += 2
                continue
            if content[i] == '"':
                return i + 1
            i += 1
        return len(content)

    def _find_char_end(self, content: str, start: int) -> int:
        i = start
        while i < len(content):
            if content[i] == '\\':
                i += 2
                continue
            if content[i] == "'":
                return i + 1
            i += 1
        return len(content)
