"""
string_indexof_range_transform.py

Optional Java 21 optimization (String.indexOf(x, beginIndex, endIndex), new in Java 21):

    s.substring(a, b).indexOf(x) >= 0        ->   s.indexOf(x, a, b) >= 0
    s.substring(a, b).contains("t")          ->   (s.indexOf("t", a, b) >= 0)

Why it is faster / lighter
    substring() COPIES the characters between a and b into a new String (time O(b-a),
    extra memory O(b-a)). The range form searches in place: no copy, no garbage.

Safety rules (anything else is left untouched)
    * only when the RESULT IS COMPARED WITH -1 / 0 (found / not found), because the
      returned position of the range form is relative to the whole string, not to the substring
    * s is declared in this file ONLY as String
    * a and b are side-effect free: identifiers, integers, +, - and .length()
    * for contains(): the argument is a String literal or a String variable
    * invalid ranges throw StringIndexOutOfBoundsException in both versions
"""
from __future__ import annotations

# (embedded at the top of every new transformer so each file is self-contained)
import re

_KEYWORDS = {"return", "else", "new", "throw", "case", "assert", "yield",
             "instanceof", "import", "package", "goto", "do", "in"}


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


def _types_in_scope(masked: str, name: str, pos: int) -> set:
    """Types of the variable `name` that are IN SCOPE at position `pos`
    (locals, parameters, for/catch variables, fields declared above).
    Empty set = no visible declaration found (callers then leave the code alone)."""
    # block ranges and parenthesis pairs
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

    decl = re.compile(r'(?<![\w$.])([A-Za-z_$][\w$]*)(?:\s*<[^;(){}=]*?>)?(?:\s*\[\s*\])*\s+'
                      + re.escape(name) + r'\s*(?P<end>=|;|,|\)|:)')
    found = set()
    for m in decl.finditer(masked):
        typ, p = m.group(1), m.start()
        if typ in _KEYWORDS or p >= pos:
            continue
        # inside a ( ... ) group?  -> parameter / for / catch / try-resource variable
        group = [(o, c) for o, c in parens.items() if o < p < c]
        if group:
            o, c = min(group, key=lambda oc: oc[1] - oc[0])
            rest = masked[c + 1:]
            j = c + 1 + (len(rest) - len(rest.lstrip()))
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
_ATOM = rf"(?:{_IDENT}(?:\s*\.\s*length\s*\(\s*\))?|\d+)"
_ARITH = rf"{_ATOM}(?:\s*[+\-]\s*{_ATOM})*"
_NEEDLE = rf"(?:{_IDENT}|\"[^\"\n]*\"|\'[^\'\n]*\')"
_CMP = r"(?:>=\s*0|>\s*-\s*1|!=\s*-\s*1|==\s*-\s*1|<\s*0|<=\s*-\s*1)"

_RX = re.compile(
    rf"(?<![\w$.])(?P<recv>{_IDENT})\s*\.\s*substring\s*\(\s*(?P<a>{_ARITH})\s*,\s*(?P<b>{_ARITH})\s*\)"
    rf"\s*\.\s*(?P<m>indexOf|contains)\s*\(\s*(?P<x>{_NEEDLE})\s*\)"
    rf"(?P<cmp>\s*{_CMP})?"
)


class StringIndexOfRangeTransformer:
    NAME = "String.substring(a,b).indexOf/contains -> String.indexOf(x, a, b)"

    def transform(self, content: str):
        masked = _mask(content)
        edits = []

        for m in _RX.finditer(masked):
            recv, method = m.group("recv"), m.group("m")
            if _types_in_scope(masked, recv, m.start()) != {"String"}:
                continue

            a = content[m.start("a"):m.end("a")].strip()
            b = content[m.start("b"):m.end("b")].strip()
            x = content[m.start("x"):m.end("x")]

            if method == "indexOf":
                if not m.group("cmp"):
                    continue                       # position is used -> offset differs, leave it
                cmp_text = content[m.start("cmp"):m.end("cmp")]
                new = f"{recv}.indexOf({x}, {a}, {b}){cmp_text}"
            else:                                  # contains
                if m.group("cmp"):
                    continue
                if not x.startswith('"') and _types_in_scope(masked, x, m.start()) != {"String"}:
                    continue                       # contains(CharSequence) vs indexOf(String)
                new = f"({recv}.indexOf({x}, {a}, {b}) >= 0)"

            edits.append((m.start(), m.end(), new,
                          f"Replaced {recv}.substring({a}, {b}).{method}(...) with {recv}.indexOf(..., {a}, {b}) (no substring copy)"))

        changes = []
        for s, e, text, msg in sorted(edits, key=lambda t: t[0], reverse=True):
            content = content[:s] + text + content[e:]
            changes.append(msg)
        return content, list(reversed(changes))
