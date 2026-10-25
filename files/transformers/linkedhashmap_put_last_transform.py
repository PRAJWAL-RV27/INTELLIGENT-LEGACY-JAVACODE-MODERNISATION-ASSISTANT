"""
linkedhashmap_put_last_transform.py

Optional Java 21 optimization (SequencedMap.putLast, new in Java 21):

    map.remove(key);
    map.put(key, value);          // "move this entry to the end"

becomes:

    map.putLast(key, value);

Why it is faster / lighter
    One hash lookup instead of two, and the existing entry node is moved to the end
    instead of being discarded and a new node allocated (less garbage).

Safety rules (anything else is left untouched)
    * map is declared in this file ONLY as LinkedHashMap / SequencedMap
    * the two statements are back to back, with the SAME map and the SAME key
    * key and value are simple (identifiers, literals, field access, + - *): no method calls,
      so evaluating value after remove() cannot behave differently
    * the file does not contain removeEldestEntry (an LRU cache hook: putLast on an existing
      key does not call it, remove+put on the new node does)
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
_SIMPLE = r"(?:[\w$.]+|\"[^\"\n]*\"|\'[^\'\n]*\')"
_VALUE = rf"{_SIMPLE}(?:\s*[+\-*]\s*{_SIMPLE})*"

_RX = re.compile(
    rf"(?<![\w$.])(?P<m>{_IDENT})\s*\.\s*remove\s*\(\s*(?P<k1>{_SIMPLE})\s*\)\s*;\s*"
    rf"(?P=m)\s*\.\s*put\s*\(\s*(?P<k2>{_SIMPLE})\s*,\s*(?P<v>{_VALUE})\s*\)\s*;"
)


class LinkedHashMapPutLastTransformer:
    NAME = "LinkedHashMap remove(k)+put(k,v) -> putLast(k,v)"

    def transform(self, content: str):
        if "removeEldestEntry" in content:
            return content, []

        masked = _mask(content)
        edits = []

        for m in _RX.finditer(masked):
            mp = m.group("m")
            types = _types_in_scope(masked, mp, m.start())
            if not types or not types <= {"LinkedHashMap", "SequencedMap"}:
                continue

            k1 = content[m.start("k1"):m.end("k1")].strip()
            k2 = content[m.start("k2"):m.end("k2")].strip()
            v = content[m.start("v"):m.end("v")].strip()
            if k1 != k2:                                   # compare the ORIGINAL text (not the masked one)
                continue
            if re.search(rf"(?<![\w$.]){re.escape(mp)}(?![\w$])", masked[m.start("v"):m.end("v")]):
                continue

            edits.append((m.start(), m.end(), f"{mp}.putLast({k1}, {v});",
                          f"Replaced {mp}.remove({k1}) + {mp}.put(...) with {mp}.putLast(...)"))

        changes = []
        for s, e, text, msg in sorted(edits, key=lambda t: t[0], reverse=True):
            content = content[:s] + text + content[e:]
            changes.append(msg)
        return content, list(reversed(changes))
