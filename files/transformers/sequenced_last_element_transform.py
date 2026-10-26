"""
sequenced_last_element_transform.py

Optional Java 21 optimization (SequencedCollection.getLast(), new in Java 21):

    String last = null;
    for (String x : items) { last = x; }

becomes:

    String last = items.isEmpty() ? null : items.getLast();

Why it is faster
    The loop walks the WHOLE collection just to keep the final element: O(n).
    getLast() jumps straight to it: O(1) (O(log n) for a TreeSet).

Safety rules (anything else is left untouched)
    * the loop body is exactly  last = x;
    * the start value is null or a String literal, and the variable types are reference
      types (a primitive would unbox every element in the old loop but only the last one
      in the new code, which changes when a NullPointerException happens)
    * the collection is declared in this file ONLY as List, ArrayList, LinkedList, Vector,
      Deque, ArrayDeque, LinkedHashSet, TreeSet, SortedSet, NavigableSet, SequencedSet or
      SequencedCollection (all have a defined order and getLast() in Java 21)
    * an empty collection gives the start value, exactly like the old loop
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
_TYPE = rf"{_IDENT}(?:\s*\.\s*{_IDENT})*(?:\s*<[^;(){{}}=]*>)?(?:\s*\[\s*\])*"

_RX = re.compile(
    rf"(?P<type>{_TYPE})\s+(?P<last>{_IDENT})\s*=\s*(?P<init>null|\"[^\"\n]*\")\s*;\s*"
    rf"for\s*\(\s*(?:final\s+)?(?P<t2>{_TYPE})\s+(?P<x>{_IDENT})\s*:\s*(?P<src>{_IDENT})\s*\)\s*"
    rf"(?:\{{\s*(?P=last)\s*=\s*(?P=x)\s*;\s*\}}|(?P=last)\s*=\s*(?P=x)\s*;)"
)

_OK_TYPES = {"List", "ArrayList", "LinkedList", "Vector", "Deque", "ArrayDeque", "LinkedHashSet",
             "TreeSet", "SortedSet", "NavigableSet", "SequencedSet", "SequencedCollection"}


class SequencedLastElementTransformer:
    NAME = "Loop that keeps the last element -> getLast()"

    def transform(self, content: str):
        masked = _mask(content)
        edits, changes = [], []

        for m in _RX.finditer(masked):
            first = lambda g: re.match(r"[A-Za-z_$][\w$]*", masked[m.start(g):m.end(g)]).group(0)
            if first("type") in _PRIMITIVES | _KEYWORDS or first("t2") in _PRIMITIVES | _KEYWORDS:
                continue
            src = m.group("src")
            types = _types_in_scope(masked, src, m.start())
            if not types or not types <= _OK_TYPES:
                continue

            typ = content[m.start("type"):m.end("type")]
            last = m.group("last")
            init = content[m.start("init"):m.end("init")]
            new = f"{typ} {last} = {src}.isEmpty() ? {init} : {src}.getLast();"
            edits.append((m.start(), m.end(), new))
            changes.append(f"Replaced full loop over '{src}' with {src}.getLast() (O(n) -> O(1))")

        for s, e, text in sorted(edits, key=lambda t: t[0], reverse=True):
            content = content[:s] + text + content[e:]
        return content, changes
