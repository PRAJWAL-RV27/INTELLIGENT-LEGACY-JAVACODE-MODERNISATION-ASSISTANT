import re

from .base_transformer import BaseTransformer


class JavaxActivationToJakartaTransformer(BaseTransformer):
    """Safely migrate javax.activation.* package references to jakarta.activation.*."""

    OLD_PACKAGE = "javax.activation"
    NEW_PACKAGE = "jakarta.activation"

    def transform(self, content: str) -> tuple[str, list[str]]:
        if self.OLD_PACKAGE not in content:
            return content, []

        transformed = self._rewrite_code_only(content)
        transformed = self._dedupe_jakarta_activation_imports(transformed)

        if transformed == content:
            return content, []

        report_entries = []
        for old_api in sorted(self._extract_code_references(content)):
            new_api = old_api.replace(self.OLD_PACKAGE, self.NEW_PACKAGE, 1)
            report_entries.append(
                f"Original API: {old_api}; Replacement API: {new_api}; "
                "Reason: Java 8 → Java 21 package migration; Action: AUTOMATED"
            )

        return transformed, report_entries

    def _rewrite_code_only(self, content: str) -> str:
        out: list[str] = []
        i = 0
        while i < len(content):
            special = self._next_special_index(content, i)
            if special is None:
                out.append(self._replace_package_reference(content[i:]))
                break

            if special > i:
                out.append(self._replace_package_reference(content[i:special]))

            token = self._read_special_token(content, special)
            if token is None:
                out.append(content[special])
                i = special + 1
                continue

            out.append(token)
            i = special + len(token)

        return "".join(out)

    def _replace_package_reference(self, segment: str) -> str:
        return re.sub(
            r"(?<![A-Za-z0-9_])javax\.activation(?![A-Za-z0-9_])",
            self.NEW_PACKAGE,
            segment,
        )

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
        for match in re.finditer(r"javax\.activation(?:\.(?:\*|[A-Za-z_][A-Za-z0-9_]*))?", segment):
            value = match.group(0)
            if value.endswith(".*"):
                matches.add("javax.activation.*")
            elif value.startswith("javax.activation."):
                matches.add(value)
            else:
                matches.add("javax.activation")

    def _dedupe_jakarta_activation_imports(self, content: str) -> str:
        seen: set[str] = set()
        lines = content.splitlines(True)
        result: list[str] = []

        for line in lines:
            stripped = line.strip()
            if stripped.startswith("import ") and "jakarta.activation" in stripped:
                if stripped in seen:
                    continue
                seen.add(stripped)
            result.append(line)

        return "".join(result)
