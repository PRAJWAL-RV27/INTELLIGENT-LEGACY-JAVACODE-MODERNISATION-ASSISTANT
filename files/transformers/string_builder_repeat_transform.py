"""
string_builder_repeat_transform.py

Optional Java 21 optimization (StringBuilder.repeat / StringBuffer.repeat, new in Java 21):

    for (int i = 0; i < n; i++) sb.append("-");

becomes:

    sb.repeat("-", n);

Why it is faster / lighter
    repeat() grows the buffer ONCE and fills it in bulk, instead of n separate
    append() calls (n bounds/capacity checks and several re-allocations while growing).

Safety rules (anything else is left untouched)
    * the loop is exactly  for (int i = 0; i < N; i++)  with ONLY  sb.append(<literal>);  inside
    * the appended value is a String literal or a char literal (an int/variable would change meaning)
    * sb is declared in this file ONLY as StringBuilder / StringBuffer
    * N is a non-negative int literal, or a variable declared ONLY as int.
      A variable is wrapped as Math.max(0, N) because the loop does nothing for N < 0
      while repeat() would throw.
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

_APPEND = rf"(?P<sb>{_IDENT})\s*\.\s*append\s*\(\s*(?P<lit>\"[^\"\n]*\"|\'[^\'\n]*\')\s*\)\s*;"
_HEAD = (rf"\bfor\s*\(\s*int\s+(?P<i>{_IDENT})\s*=\s*0\s*;\s*(?P=i)\s*<\s*(?P<n>\d+|{_IDENT})\s*;\s*"
         rf"(?:(?P=i)\s*\+\+|\+\+\s*(?P=i))\s*\)\s*")
_LOOPS = [re.compile(_HEAD + r"\{\s*" + _APPEND + r"\s*\}"),     # braced body
          re.compile(_HEAD + _APPEND)]                              # single statement


class StringBuilderRepeatTransformer:
    NAME = "StringBuilder append-loop -> StringBuilder.repeat()"

    def transform(self, content: str):
        masked = _mask(content)
        edits = []          # (start, end, replacement, message)

        for rx in _LOOPS:
            for m in rx.finditer(masked):
                sb, n = m.group("sb"), m.group("n")

                types = _types_in_scope(masked, sb, m.start())
                if not types or not types <= {"StringBuilder", "StringBuffer"}:
                    continue

                if n.isdigit():
                    count = n
                else:
                    ntypes = _types_in_scope(masked, n, m.start())
                    if ntypes != {"int"}:
                        continue
                    count = f"Math.max(0, {n})"

                lit = content[m.start("lit"):m.end("lit")]       # original literal text
                if any(m.start() < e and s < m.end() for s, e, _, _ in edits):
                    continue                                       # already handled by the other regex
                edits.append((m.start(), m.end(), f"{sb}.repeat({lit}, {count});",
                              f"Replaced append loop on '{sb}' with {sb}.repeat({lit}, {n})"))

        edits.sort(key=lambda e: e[0], reverse=True)
        changes = []
        for s, e, text, msg in edits:
            content = content[:s] + text + content[e:]
            changes.append(msg)
        return content, list(reversed(changes))
