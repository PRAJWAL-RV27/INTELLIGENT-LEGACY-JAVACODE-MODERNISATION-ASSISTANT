"""
list_reverse_loop_transform.py

Optional Java 21 optimization (List.reversed(), new in Java 21):

    for (int i = list.size() - 1; i >= 0; i--) {
        T x = list.get(i);
        ...
    }

becomes:

    for (T x : list.reversed()) {
        ...
    }

Why it is faster
    On a LinkedList every get(i) walks the chain: the loop is O(n^2). reversed() walks
    the list once, backwards: O(n). On an ArrayList it is the same O(n) (no loss).

Safety rules (anything else is left untouched)
    * the loop has exactly this shape, and its first statement is  T x = list.get(i);
    * the loop variable i and the list are NOT mentioned anywhere else in the loop body
      (so the body cannot modify the list or depend on the index)
    * list is declared in this file ONLY as List / ArrayList / LinkedList / Vector
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
_TYPE = rf"{_IDENT}(?:\s*\.\s*{_IDENT})*(?:\s*<[^;(){{}}=]*>)?(?:\s*\[\s*\])*"

_RX = re.compile(
    rf"\bfor\s*\(\s*int\s+(?P<i>{_IDENT})\s*=\s*(?P<l>{_IDENT})\s*\.\s*size\s*\(\s*\)\s*-\s*1\s*;\s*"
    rf"(?P=i)\s*>=\s*0\s*;\s*(?:(?P=i)\s*--|--\s*(?P=i))\s*\)\s*(?P<open>\{{)\s*"
    rf"(?P<mods>(?:final\s+)?)(?P<type>{_TYPE})\s+(?P<x>{_IDENT})\s*=\s*(?P=l)\s*\.\s*get\s*\(\s*(?P=i)\s*\)\s*;"
)

_OK_TYPES = {"List", "ArrayList", "LinkedList", "Vector"}


class ListReverseLoopTransformer:
    NAME = "Index-based reverse loop over List -> List.reversed() for-each"

    def transform(self, content: str):
        masked = _mask(content)
        edits, changes = [], []

        for m in _RX.finditer(masked):
            lst, i = m.group("l"), m.group("i")
            types = _types_in_scope(masked, lst, m.start())
            if not types or not types <= _OK_TYPES:
                continue

            close = _match_brace(masked, m.start("open"))
            if close == -1:
                continue
            body_masked = masked[m.end():close]
            if re.search(rf"(?<![\w$.]){re.escape(i)}(?![\w$])", body_masked):
                continue                                   # index used in the body
            if re.search(rf"(?<![\w$]){re.escape(lst)}(?![\w$])", body_masked):
                continue                                   # list touched in the body

            if any(m.start() < e and s < close + 1 for s, e, _ in edits):
                continue                                   # nested inside a loop we already rewrite
            mods, typ, x = m.group("mods"), content[m.start("type"):m.end("type")], m.group("x")
            new_head = f"for ({mods}{typ} {x} : {lst}.reversed()) {{"
            body = content[m.end():close]
            edits.append((m.start(), close + 1, new_head + body + "}"))
            changes.append(f"Replaced reverse index loop over '{lst}' with {lst}.reversed() (single backward pass)")

        for s, e, text in sorted(edits, key=lambda t: t[0], reverse=True):
            content = content[:s] + text + content[e:]
        return content, changes
