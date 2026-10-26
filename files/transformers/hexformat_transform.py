"""
hexformat_transform.py

Optional optimization with java.util.HexFormat (added in Java 17, so not in Java 8):

    StringBuilder sb = new StringBuilder();
    for (byte b : data) sb.append(String.format("%02x", b));

becomes:

    StringBuilder sb = new StringBuilder(java.util.HexFormat.of().formatHex(data));

(also the same for  "%02X"  -> withUpperCase(),  for  String hex = ""; ... hex += ...;
 and for index loops  for (int i = 0; i < data.length; i++) ... data[i])

Why it is faster / lighter
    String.format parses its format string and allocates several objects FOR EVERY BYTE.
    formatHex converts the whole array in one tight loop with a single result buffer.
    This is typically many times faster.

Safety rules (anything else is left untouched)
    * the array is declared in this file ONLY as byte[]; the loop variable is a byte
      (a byte printed with %02x gives exactly 2 hex digits, negative bytes as 00..ff;
      an int would give 8 digits, so ints are never touched)
    * the format is exactly "%02x" or "%02X", appended once per element and nothing else
      happens in the loop (written as String.format("%02x", b) or "%02x".formatted(b))
    * the builder / string is created (empty) on the line right before the loop
    * no import is needed: java.util.HexFormat is written fully qualified
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
_LIT4 = r"\"_{4}\""                                         # "%02x" / "%02X" (the inside is masked)

_FOREACH = rf"for\s*\(\s*(?:final\s+)?byte\s+(?P<b>{_IDENT})\s*:\s*(?P<arr>{_IDENT})\s*\)\s*"
_INDEX = (rf"for\s*\(\s*int\s+(?P<i>{_IDENT})\s*=\s*0\s*;\s*(?P=i)\s*<\s*(?P<arr>{_IDENT})\s*\.\s*length\s*;\s*"
          rf"(?:(?P=i)\s*\+\+|\+\+\s*(?P=i))\s*\)\s*")


def _build():
    rxs = []
    for loop, elem in ((_FOREACH, r"(?P=b)"), (_INDEX, rf"(?P=arr)\s*\[\s*(?P=i)\s*\]")):
        # both shapes: String.format("%02x", b)   and   "%02x".formatted(b)  (which an earlier
        # mandatory transformer of the tool produces)
        call = (rf"(?:String\s*\.\s*format\s*\(\s*(?P<f1>{_LIT4})\s*,\s*{elem}\s*\)"
                rf"|(?P<f2>{_LIT4})\s*\.\s*formatted\s*\(\s*{elem}\s*\))")
        # --- StringBuilder target
        sb_head = rf"StringBuilder\s+(?P<sb>{_IDENT})\s*=\s*new\s+StringBuilder\s*\(\s*(?P<cap>[^;()]*?)\s*\)\s*;\s*"
        sb_body = rf"(?P=sb)\s*\.\s*append\s*\(\s*{call}\s*\)\s*;"
        rxs.append(("sb", re.compile(sb_head + loop + r"\{\s*" + sb_body + r"\s*\}")))
        rxs.append(("sb", re.compile(sb_head + loop + sb_body)))
        # --- String target
        st_head = rf"String\s+(?P<h>{_IDENT})\s*=\s*\"\"\s*;\s*"
        for body in (rf"(?P=h)\s*\+=\s*{call}\s*;", rf"(?P=h)\s*=\s*(?P=h)\s*\+\s*{call}\s*;"):
            rxs.append(("str", re.compile(st_head + loop + r"\{\s*" + body + r"\s*\}")))
            rxs.append(("str", re.compile(st_head + loop + body)))
    return rxs


_PATTERNS = _build()


class HexFormatTransformer:
    NAME = "String.format(\"%02x\") hex loop -> HexFormat.formatHex()"

    def transform(self, content: str):
        masked = _mask(content)
        edits = []

        for kind, rx in _PATTERNS:
            for m in rx.finditer(masked):
                if any(m.start() < e and s < m.end() for s, e, _, _ in edits):
                    continue
                g = "f1" if m.group("f1") else "f2"
                fmt = content[m.start(g):m.end(g)]
                if fmt not in ('"%02x"', '"%02X"'):
                    continue
                arr = m.group("arr")
                if _types_in_scope(masked, arr, m.start()) != {"byte[]"}:
                    continue
                hexed = "java.util.HexFormat.of()" + (".withUpperCase()" if fmt == '"%02X"' else "") + f".formatHex({arr})"
                if kind == "sb":
                    new = f"StringBuilder {m.group('sb')} = new StringBuilder({hexed});"
                else:
                    new = f"String {m.group('h')} = {hexed};"
                edits.append((m.start(), m.end(), new,
                              f"Replaced per-byte String.format({fmt}) loop over '{arr}' with HexFormat.formatHex"))

        changes = []
        for s, e, text, msg in sorted(edits, key=lambda t: t[0], reverse=True):
            content = content[:s] + text + content[e:]
            changes.append(msg)
        return content, list(reversed(changes))
