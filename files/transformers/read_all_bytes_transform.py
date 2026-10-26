"""
read_all_bytes_transform.py

Optional optimization with InputStream.readAllBytes() (added in Java 9, so not in Java 8):

    ByteArrayOutputStream bos = new ByteArrayOutputStream();
    byte[] buf = new byte[8192];
    int n;
    while ((n = in.read(buf)) != -1) { bos.write(buf, 0, n); }
    return bos.toByteArray();

becomes:

    return in.readAllBytes();

(also when the last line is  byte[] data = bos.toByteArray();  and the three declarations
 come in any order before the loop)

Why it is faster / lighter
    The hand-written loop copies every chunk into the ByteArrayOutputStream (which keeps
    doubling its internal array) and toByteArray() copies everything once more.
    readAllBytes() reads straight into exactly-sized buffers (and for a ByteArrayInputStream
    or FileInputStream it knows the size up front), so far less copying and garbage.

Safety rules (anything else is left untouched)
    * the loop is exactly  while ((n = in.read(buf)) != -1) bos.write(buf, 0, n);
    * bos, buf and n are declared right before the loop (3 statements) and are NOT used
      again after the result line
    * the stream is a variable declared in this file ONLY as InputStream, FileInputStream,
      BufferedInputStream, ByteArrayInputStream, DataInputStream or GZIPInputStream
      (your own InputStream subclass is never touched)
    * the buffer size is not a literal 0
    * for a ByteArrayInputStream (whose readAllBytes() declares no IOException) the loop is not
      inside a  try { } catch (IOException e)  in the same method
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
_WRITE = rf"(?P<bos>{_IDENT})\s*\.\s*write\s*\(\s*(?P=buf)\s*,\s*0\s*,\s*(?P=n)\s*\)\s*;"
_HEAD = (rf"while\s*\(\s*\(\s*(?P<n>{_IDENT})\s*=\s*(?P<inp>{_IDENT})\s*\.\s*read\s*\(\s*(?P<buf>{_IDENT})\s*\)\s*\)"
         rf"\s*!=\s*-\s*1\s*\)\s*")
_LOOPS = [re.compile(_HEAD + r"\{\s*" + _WRITE + r"\s*\}"), re.compile(_HEAD + _WRITE)]

def _inside_try_catching_ioexception(masked: str, start: int, end: int) -> bool:
    """True if [start, end) lies inside a try { } whose catch list names IOException.
    ByteArrayInputStream.readAllBytes() does NOT declare IOException (its read(byte[]) does),
    so rewriting inside such a try would give 'exception IOException is never thrown'."""
    for t in re.finditer(r"\btry\s*(?:\([^)]*\))?\s*\{", masked):
        open_idx = t.end() - 1
        close = _match_brace(masked, open_idx)
        if close != -1 and open_idx < start and end <= close:
            catches = re.match(r"(?:\s*catch\s*\([^)]*\)\s*\{[^{}]*\})*", masked[close + 1:])
            tail = masked[close + 1:close + 1 + 2000]
            if re.match(r"\s*catch\s*\([^)]*\bIOException\b", tail) or \
                    re.search(r"\}\s*catch\s*\([^)]*\bIOException\b", tail.split("finally")[0]):
                return True
    return False


_OK_STREAMS = {"InputStream", "FileInputStream", "BufferedInputStream", "ByteArrayInputStream",
               "DataInputStream", "GZIPInputStream"}


class ReadAllBytesTransformer:
    NAME = "Manual read-buffer loop into ByteArrayOutputStream -> InputStream.readAllBytes()"

    def transform(self, content: str):
        masked = _mask(content)
        edits, changes = [], []

        for rx in _LOOPS:
            for m in rx.finditer(masked):
                n, inp, buf, bos = m.group("n"), m.group("inp"), m.group("buf"), m.group("bos")
                if any(m.start() < e and s < m.end() for s, e, _ in edits):
                    continue
                if not _types_in_scope(masked, inp, m.start()) or \
                        not _types_in_scope(masked, inp, m.start()) <= _OK_STREAMS:
                    continue

                if _types_in_scope(masked, inp, m.start()) == {"ByteArrayInputStream"} and \
                        _inside_try_catching_ioexception(masked, m.start(), m.end()):
                    continue

                # ---- the line after the loop: the result
                tail = re.compile(
                    rf"\s*(?:return\s+{re.escape(bos)}\s*\.\s*toByteArray\s*\(\s*\)\s*;"
                    rf"|byte\s*\[\s*\]\s+(?P<res>{_IDENT})\s*=\s*{re.escape(bos)}\s*\.\s*toByteArray\s*\(\s*\)\s*;)"
                ).match(masked, m.end())
                if not tail:
                    continue

                # ---- the 3 declarations right before the loop (any order)
                decls = {"bos": rf"ByteArrayOutputStream\s+{re.escape(bos)}\s*=\s*new\s+ByteArrayOutputStream\s*\([^;()]*\)\s*;",
                         "buf": rf"byte\s*\[\s*\]\s+{re.escape(buf)}\s*=\s*new\s+byte\s*\[\s*[\w$\s*+<]+\]\s*;",
                         "n": rf"int\s+{re.escape(n)}\s*(?:=\s*\d+\s*)?;"}
                before, found, first_start, ok = masked[:m.start()], set(), None, True
                for _ in range(3):
                    mm = re.search(r"([^;{}]+;)\s*$", before)
                    if not mm:
                        ok = False
                        break
                    stmt = mm.group(1)
                    hit = [k for k, p in decls.items() if re.fullmatch(r"\s*" + p, stmt)]
                    if len(hit) != 1 or hit[0] in found:
                        ok = False
                        break
                    found.add(hit[0])
                    first_start = mm.start(1) + (len(stmt) - len(stmt.lstrip()))
                    before = before[:mm.start(1)]
                if not ok or found != {"bos", "buf", "n"}:
                    continue
                size = re.search(rf"byte\s*\[\s*{re.escape(buf)}\s*\]\s*=\s*new\s+byte\s*\[\s*([\w$\s*+<]+)\]",
                                 masked[first_start:m.start()])
                if size and size.group(1).strip() == "0":
                    continue

                # ---- bos / buf / n must not be used after the result line
                end = tail.end()
                rest = masked[end:_enclosing_block_end(masked, end)]
                if any(re.search(rf"(?<![\w$.]){re.escape(v)}(?![\w$])", rest) for v in (bos, buf, n)):
                    continue

                res = tail.group("res")
                new = f"return {inp}.readAllBytes();" if res is None else f"byte[] {res} = {inp}.readAllBytes();"
                edits.append((first_start, end, new))
                changes.append(f"Replaced manual read loop on '{inp}' with {inp}.readAllBytes()")

        for s, e, text in sorted(edits, key=lambda t: t[0], reverse=True):
            content = content[:s] + text + content[e:]
        return content, changes
