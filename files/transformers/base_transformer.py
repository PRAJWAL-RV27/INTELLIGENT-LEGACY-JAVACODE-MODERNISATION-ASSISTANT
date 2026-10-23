"""
base_transformer.py — Abstract base class every transformer must extend.

Contract that ALL subclasses must uphold
────────────────────────────────────────
  ✔  Input and output Java programs must behave identically at runtime.
  ✔  Time and space complexity of the transformed code must NOT increase.
  ✔  Only change what is strictly necessary (no cosmetic rewrites).
  ✔  If in doubt, leave the code unchanged.
"""
from abc import ABC, abstractmethod


class BaseTransformer(ABC):

    @abstractmethod
    def transform(self, content: str) -> tuple[str, list[str]]:
        """
        Args:
            content: Full Java source file as a UTF-8 string.

        Returns:
            (new_content, changes)
            where `changes` is a list of human-readable descriptions of
            every modification made (empty list = no changes).
        """



def add_import(content: str, import_name: str) -> str:
    """Insert `import <import_name>;` AFTER the package line (never above it).
    Does nothing if the import (or a wildcard for it) is already present."""
    import re
    stmt = f"import {import_name};"
    if re.search(r'^\s*import\s+' + re.escape(import_name) + r'\s*;', content, re.M):
        return content
    pkg = re.search(r'^[ \t]*package\s+[\w.]+\s*;[ \t]*\r?\n?', content, re.M)
    first_imp = re.search(r'^[ \t]*import\s', content, re.M)
    if first_imp:
        i = first_imp.start()
        return content[:i] + stmt + "\n" + content[i:]
    if pkg:
        i = pkg.end()
        return content[:i] + "\n" + stmt + "\n" + content[i:]
    return stmt + "\n" + content


def apply_to_code(content: str, fn) -> str:
    """Run fn(code_segment) -> new_code_segment ONLY on real Java code.
    Comments, string literals, text blocks and char literals are left untouched,
    so text such as "new Integer(5)" inside a string or comment is never rewritten."""
    out, i, n, start = [], 0, len(content), 0

    def flush(end):
        if end > start:
            out.append(fn(content[start:end]))

    while i < n:
        c = content[i]
        nxt = content[i + 1] if i + 1 < n else ""
        if c == "/" and nxt == "/":
            flush(i); j = content.find("\n", i); j = n if j == -1 else j
            out.append(content[i:j]); i = start = j
        elif c == "/" and nxt == "*":
            flush(i); j = content.find("*/", i + 2); j = n if j == -1 else j + 2
            out.append(content[i:j]); i = start = j
        elif content.startswith('"""', i):
            flush(i); j = content.find('"""', i + 3); j = n if j == -1 else j + 3
            out.append(content[i:j]); i = start = j
        elif c in "\"'":
            flush(i); j = i + 1
            while j < n and content[j] != c and content[j] != "\n":
                j += 2 if content[j] == "\\" else 1
            j = min(j + 1, n)
            out.append(content[i:j]); i = start = j
        else:
            i += 1
    flush(n)
    return "".join(out)
