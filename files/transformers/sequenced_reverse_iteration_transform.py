"""
sequenced_reverse_iteration_transform.py

Optional Java 21 optimization (reversed() on sequenced Sets and Deques, new in Java 21):

    List<T> tmp = new ArrayList<>(set);
    Collections.reverse(tmp);
    for (T x : tmp) { ... }

becomes:

    for (T x : set.reversed()) { ... }

Why it is faster / lighter
    The old code copies the whole collection (O(n) time AND O(n) memory) and then
    reverses the copy (another O(n) pass). reversed() is a zero-copy view.

Safety rules (anything else is left untouched)
    * the source is declared in this file ONLY as LinkedHashSet, TreeSet, SortedSet,
      NavigableSet, SequencedSet, SequencedCollection, Deque or ArrayDeque
      (plain List is handled by the separate List transformer; HashSet has no order)
    * the temporary list is used ONLY by this reverse + for-each (its name never appears again)
    * the loop body does not mention the source collection or the temporary list
      (a view reflects later changes, a copy would not)
    * the for-each loop has a { } body
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
    rf"List\s*<[^;(){{}}=]*>\s+(?P<tmp>{_IDENT})\s*=\s*new\s+ArrayList\s*(?:<[^;(){{}}=]*>)?\s*"
    rf"\(\s*(?P<src>{_IDENT})\s*\)\s*;\s*"
    rf"Collections\s*\.\s*reverse\s*\(\s*(?P=tmp)\s*\)\s*;\s*"
    rf"for\s*\(\s*(?P<mods>(?:final\s+)?)(?P<type>{_TYPE})\s+(?P<x>{_IDENT})\s*:\s*(?P=tmp)\s*\)\s*(?P<open>\{{)"
)

_OK_TYPES = {"LinkedHashSet", "TreeSet", "SortedSet", "NavigableSet", "SequencedSet",
             "SequencedCollection", "Deque", "ArrayDeque"}


class SequencedReverseIterationTransformer:
    NAME = "Reverse copy of Set/Deque + for-each -> reversed() view"

    def transform(self, content: str):
        masked = _mask(content)
        edits, changes = [], []

        for m in _RX.finditer(masked):
            tmp, src = m.group("tmp"), m.group("src")
            types = _types_in_scope(masked, src, m.start())
            if not types or not types <= _OK_TYPES:
                continue

            close = _match_brace(masked, m.start("open"))
            if close == -1:
                continue
            body_masked = masked[m.end():close]
            word = lambda w: re.compile(rf"(?<![\w$.]){re.escape(w)}(?![\w$])")
            if word(src).search(body_masked) or word(tmp).search(body_masked):
                continue
            if word(tmp).search(masked[close + 1:]):
                continue                                   # the copy is used again later

            if any(m.start() < e and s < close + 1 for s, e, _ in edits):
                continue
            mods, typ, x = m.group("mods"), content[m.start("type"):m.end("type")], m.group("x")
            body = content[m.end():close]
            edits.append((m.start(), close + 1,
                          f"for ({mods}{typ} {x} : {src}.reversed()) {{" + body + "}"))
            changes.append(f"Replaced reversed copy of '{src}' with {src}.reversed() (no copy)")

        for s, e, text in sorted(edits, key=lambda t: t[0], reverse=True):
            content = content[:s] + text + content[e:]
        return content, changes
