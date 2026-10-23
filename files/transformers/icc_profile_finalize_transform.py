import re

from .base_transformer import BaseTransformer


class ICCProfileFinalizeManualReviewTransformer(BaseTransformer):
    """Report ICC_Profile.finalize() usage without changing Java source."""

    TARGET_TYPE = "java.awt.color.ICC_Profile"
    REPORT_REASON = (
        "ICC_Profile.finalize() was removed from the JDK; no direct replacement exists"
    )

    def transform(self, content: str) -> tuple[str, list[str]]:
        if "ICC_Profile" not in content and "java.awt.color.ICC_Profile" not in content:
            return content, []

        matches = self._detect_code_references(content)
        if not matches:
            return content, []

        report_entries = []
        for api in sorted(matches):
            report_entries.append(
                f"Original API: {api}; Replacement API: None; "
                f"Reason: {self.REPORT_REASON}; Action: MANUAL_REVIEW"
            )

        return content, report_entries

    def _detect_code_references(self, content: str) -> set[str]:
        matches: set[str] = set()
        known_names = self._collect_known_profile_names(content)

        for code_segment in self._iter_code_segments(content):
            # 1. profile.finalize()
            for match in re.finditer(
                r"(?P<name>\b[A-Za-z_][A-Za-z0-9_]*\b)"
                r"(?P<dot>\s*\.\s*)"
                r"finalize"
                r"(?P<parens>\s*\(\s*\))",
                code_segment,
            ):
                name = match.group("name")
                if name in known_names:
                    matches.add(f"{self.TARGET_TYPE}.finalize()")

            # 2. new ICC_Profile(...).finalize()
            for match in re.finditer(
                r"(?P<receiver>new\s+(?:java\.awt\.color\.)?ICC_Profile\s*\([^)]*\))"
                r"(?P<dot>\s*\.\s*)"
                r"finalize"
                r"(?P<parens>\s*\(\s*\))",
                code_segment,
            ):
                matches.add(f"{self.TARGET_TYPE}.finalize()")

        return matches

    def _collect_known_profile_names(self, content: str) -> set[str]:
        names: set[str] = set()
        for code_segment in self._iter_code_segments(content):
            for match in re.finditer(
                r"(?:^|[^A-Za-z0-9_])"
                r"(?:java\.awt\.color\.)?ICC_Profile"
                r"(?:\s*\[\s*\])?"
                r"\s+"
                r"([A-Za-z_][A-Za-z0-9_]*)",
                code_segment,
            ):
                names.add(match.group(1))
        return names

    def _iter_code_segments(self, content: str):
        i = 0
        while i < len(content):
            special = self._next_special_index(content, i)
            if special is None:
                yield content[i:]
                break

            if special > i:
                yield content[i:special]

            token = self._read_special_token(content, special)
            if token is None:
                i = special + 1
                continue
            i = special + len(token)

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
