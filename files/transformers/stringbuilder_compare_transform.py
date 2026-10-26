"""
stringbuilder_compare_transform.py

Optional optimization with StringBuilder.compareTo() (added in Java 11, so not in Java 8):

    a.toString().compareTo(b.toString())     ->   a.compareTo(b)
    a.toString().equals(b.toString())        ->   (a.compareTo(b) == 0)

Why it is lighter / faster
    toString() COPIES the whole builder into a new String. Comparing two builders this way
    makes two full copies (time and memory O(n) each) before the first character is compared.
    compareTo() compares the characters in place, and stops at the first difference.

Safety rules (anything else is left untouched)
    * a and b are variables declared in this file ONLY as StringBuilder (both) or ONLY as
      StringBuffer (both); compareTo does not accept the other type
    * the returned number is exactly the same as String.compareTo (same characters compared,
      same difference returned)
    * a null builder throws NullPointerException in both versions
"""
from __future__ import annotations

import re

_KEYWORDS = {"return", "else", "new", "throw", "case", "assert", "yield",
             "instanceof", "import", "package", "goto", "do", "in"}
_PRIMITIVES = {"int", "long", "short", "byte", "char", "boolean", "float", "double"}


def _mask(src: str) -> str:
    """Same-length copy of `src` where comments become spaces and the inside of
    string / char literals / text blocks becomes '_'. Regexes run on this copy, so
    text inside strings or comments can never be matched; positions still line up
    with the original source."""
    out, i, n = [], 0, len(src)
    while i < n:
        c, nx = src[i], (src[i + 1] if i + 1 < n else "")
        if c == "/" and nx == "/":
            j = src.find("\n", i)
            j = n if j == -1 else j
            out.append(" " * (j - i)); i = j
        elif c == "/" and nx == "*":
            j = src.find("*/", i + 2)
            j = n if j == -1 else j + 2
            out.append("".join(ch if ch == "\n" else " " for ch in src[i:j])); i = j
        elif src.startswith('"""', i):
            j = src.find('"""', i + 3)
            j = n if j == -1 else j + 3
            out.append('"""' + "".join("\n" if ch == "\n" else "_" for ch in src[i + 3:j - 3]) + '"""'); i = j
        elif c in "\"'":
            j = i + 1
            while j < n and src[j] != c and src[j] != "\n":
                j += 2 if src[j] == "\\" else 1
            j = min(j, n - 1)
            out.append(c + "_" * (j - i - 1) + (src[j] if j < n else "")); i = j + 1
        else:
            out.append(c); i += 1
    return "".join(out)


def _match_brace(masked: str, open_idx: int) -> int:
    """Index of the '}' matching the '{' at open_idx (or -1)."""
    depth = 0
    for k in range(open_idx, len(masked)):
        if masked[k] == "{":
            depth += 1
        elif masked[k] == "}":
            depth -= 1
            if depth == 0:
                return k
    return -1


def _enclosing_block_end(masked: str, pos: int) -> int:
    """Index of the '}' that closes the innermost block containing `pos`."""
    stack, best = [], len(masked)
    for k, ch in enumerate(masked):
        if ch == "{":
            stack.append(k)
        elif ch == "}" and stack:
            o = stack.pop()
            if o < pos < k and k < best:
                best = k
    return best


def _types_in_scope(masked: str, name: str, pos: int) -> set:
    """Types of the variable `name` that are IN SCOPE at position `pos` (locals,
    parameters, for/catch variables, fields declared above). Arrays are reported
    with [] (for example 'byte[]'). Empty set = no visible declaration found
    (callers then leave the code alone)."""
    blocks, stack = [], []
    for k, ch in enumerate(masked):
        if ch == "{":
            stack.append(k)
        elif ch == "}" and stack:
            blocks.append((stack.pop(), k))
    parens, pstack = {}, []
    for k, ch in enumerate(masked):
        if ch == "(":
            pstack.append(k)
        elif ch == ")" and pstack:
            parens[pstack.pop()] = k

    decl = re.compile(r'(?<![\w$.])([A-Za-z_$][\w$]*)(?:\s*<[^;(){}=]*?>)?((?:\s*\[\s*\])*)\s+'
                      + re.escape(name) + r'\s*(?:=|;|,|\)|:)')
    found = set()
    for m in decl.finditer(masked):
        typ, p = m.group(1), m.start()
        if typ in _KEYWORDS or p >= pos:
            continue
        typ += "[]" * m.group(2).count("[")
        group = [(o, c) for o, c in parens.items() if o < p < c]
        if group:
            o, c = min(group, key=lambda oc: oc[1] - oc[0])
            rest = masked[c + 1:]
            j = c + 1 + (len(rest) - len(rest.lstrip()))
            th = re.compile(r'throws\s+[\w$.\s,]+').match(masked, j)      # skip "throws X, Y" before the body
            if th:
                j = th.end()
                j += len(masked[j:]) - len(masked[j:].lstrip())
            if j < len(masked) and masked[j] == "{":
                end = next((cl for op, cl in blocks if op == j), len(masked))
            else:
                semi = masked.find(";", j)
                end = len(masked) if semi == -1 else semi
        else:
            enc = [(o, c) for o, c in blocks if o < p < c]
            end = min(enc, key=lambda oc: oc[1] - oc[0])[1] if enc else len(masked)
        if p < pos <= end:
            found.add(typ)
    return found

_IDENT = r"[A-Za-z_$][\w$]*"

_RX = re.compile(
    rf"(?<![\w$.])(?P<a>{_IDENT})\s*\.\s*toString\s*\(\s*\)\s*\.\s*(?P<m>compareTo|equals)\s*\(\s*"
    rf"(?P<b>{_IDENT})\s*\.\s*toString\s*\(\s*\)\s*\)"
)


class StringBuilderCompareTransformer:
    NAME = "StringBuilder.toString().compareTo/equals -> StringBuilder.compareTo()"

    def transform(self, content: str):
        masked = _mask(content)
        edits = []

        for m in _RX.finditer(masked):
            a, b, method = m.group("a"), m.group("b"), m.group("m")
            ta = _types_in_scope(masked, a, m.start())
            tb = _types_in_scope(masked, b, m.start())
            if not ((ta == {"StringBuilder"} and tb == {"StringBuilder"}) or
                    (ta == {"StringBuffer"} and tb == {"StringBuffer"})):
                continue
            new = f"{a}.compareTo({b})" if method == "compareTo" else f"({a}.compareTo({b}) == 0)"
            edits.append((m.start(), m.end(), new,
                          f"Replaced {a}.toString().{method}({b}.toString()) with {a}.compareTo({b}) (no copies)"))

        changes = []
        for s, e, text, msg in sorted(edits, key=lambda t: t[0], reverse=True):
            content = content[:s] + text + content[e:]
            changes.append(msg)
        return content, list(reversed(changes))
