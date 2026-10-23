import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from .base_transformer import BaseTransformer


CALL_NAME = "createDragSourceContext"

_CALL_HEAD = re.compile(
    r"\." + re.escape(CALL_NAME) + r"\s*\("
)

_JAVA_KEYWORDS_INVALID_AS_RECEIVER = {
    "return", "new", "throw", "else", "if", "while", "for",
    "do", "case", "yield", "assert",
}


@dataclass(frozen=True)
class CallSite:
    start: int
    end: int
    receiver: str
    args: Tuple[str, ...]
    kind: str
    line_no: int


def _build_lexical_spans(content: str) -> List[Tuple[int, int]]:
    """Return spans occupied by strings, chars, and Java comments."""
    spans: List[Tuple[int, int]] = []
    i = 0
    n = len(content)

    while i < n:
        # Java text block
        if content.startswith('"""', i):
            start = i
            i += 3
            while i < n:
                if content.startswith('"""', i):
                    i += 3
                    break
                if content[i] == "\\":
                    i += 2
                else:
                    i += 1
            spans.append((start, i))
            continue

        c = content[i]

        if c in ('"', "'"):
            quote = c
            start = i
            i += 1
            while i < n:
                if content[i] == "\\":
                    i += 2
                    continue
                if content[i] == quote:
                    i += 1
                    break
                i += 1
            spans.append((start, i))
            continue

        if c == "/" and i + 1 < n and content[i + 1] == "/":
            start = i
            newline = content.find("\n", i + 2)
            i = n if newline == -1 else newline
            spans.append((start, i))
            continue

        if c == "/" and i + 1 < n and content[i + 1] == "*":
            start = i
            end = content.find("*/", i + 2)
            i = n if end == -1 else end + 2
            spans.append((start, i))
            continue

        i += 1

    return spans


def _pos_in_any_span(
    pos: int,
    spans: List[Tuple[int, int]],
) -> bool:
    return any(start <= pos < end for start, end in spans)


def _find_matching_paren(
    content: str,
    open_idx: int,
) -> Optional[int]:
    """Find the ')' matching open_idx, ignoring comments and literals."""
    depth = 0
    i = open_idx
    n = len(content)

    while i < n:
        if content.startswith('"""', i):
            i += 3
            while i < n:
                if content.startswith('"""', i):
                    i += 3
                    break
                if content[i] == "\\":
                    i += 2
                else:
                    i += 1
            continue

        c = content[i]

        if c in ('"', "'"):
            quote = c
            i += 1
            while i < n:
                if content[i] == "\\":
                    i += 2
                    continue
                if content[i] == quote:
                    i += 1
                    break
                i += 1
            continue

        if c == "/" and i + 1 < n and content[i + 1] == "/":
            newline = content.find("\n", i + 2)
            i = n if newline == -1 else newline
            continue

        if c == "/" and i + 1 < n and content[i + 1] == "*":
            end = content.find("*/", i + 2)
            i = n if end == -1 else end + 2
            continue

        if c == "(":
            depth += 1
        elif c == ")":
            depth -= 1
            if depth == 0:
                return i
            if depth < 0:
                return None

        i += 1

    return None


def _split_top_level_arguments(
    content: str,
    start: int,
    end: int,
) -> Optional[List[str]]:
    """Split arguments at top-level commas without changing their text."""
    args: List[str] = []
    arg_start = start
    paren = bracket = brace = 0
    i = start

    while i < end:
        if content.startswith('"""', i):
            i += 3
            while i < end:
                if content.startswith('"""', i):
                    i += 3
                    break
                if content[i] == "\\":
                    i += 2
                else:
                    i += 1
            continue

        c = content[i]

        if c in ('"', "'"):
            quote = c
            i += 1
            while i < end:
                if content[i] == "\\":
                    i += 2
                    continue
                if content[i] == quote:
                    i += 1
                    break
                i += 1
            continue

        if c == "/" and i + 1 < end and content[i + 1] == "/":
            newline = content.find("\n", i + 2, end)
            i = end if newline == -1 else newline
            continue

        if c == "/" and i + 1 < end and content[i + 1] == "*":
            close = content.find("*/", i + 2, end)
            if close == -1:
                return None
            i = close + 2
            continue

        if c == "(":
            paren += 1
        elif c == ")":
            if paren == 0:
                return None
            paren -= 1
        elif c == "[":
            bracket += 1
        elif c == "]":
            if bracket == 0:
                return None
            bracket -= 1
        elif c == "{":
            brace += 1
        elif c == "}":
            if brace == 0:
                return None
            brace -= 1
        elif c == "," and paren == 0 and bracket == 0 and brace == 0:
            part = content[arg_start:i].strip()
            if not part:
                return None
            args.append(part)
            arg_start = i + 1

        i += 1

    if paren or bracket or brace:
        return None

    tail = content[arg_start:end].strip()
    if not tail:
        return [] if not args else None

    args.append(tail)
    return args


def _scan_receiver_backward(
    content: str,
    dot_idx: int,
    span_end_to_start: Dict[int, int],
) -> Optional[int]:
    """
    Conservatively find the receiver before .createDragSourceContext(...).
    """
    i = dot_idx
    depth = 0

    while i > 0:
        if i in span_end_to_start:
            i = span_end_to_start[i]
            continue

        c = content[i - 1]

        if c in ")]":
            depth += 1
            i -= 1
            continue

        if c in "([":
            if depth == 0:
                break
            depth -= 1
            i -= 1
            continue

        if depth > 0:
            i -= 1
            continue

        if c.isalnum() or c in "_.$":
            i -= 1
            continue

        break

    start = i
    receiver = content[start:dot_idx].strip()

    if not receiver:
        return None
    if receiver in _JAVA_KEYWORDS_INVALID_AS_RECEIVER:
        return None
    if receiver.startswith("("):
        return None

    return start


def _find_statement_boundary(
    content: str,
    spans: List[Tuple[int, int]],
    before_pos: int,
) -> int:
    span_end_to_start = {end: start for start, end in spans}
    i = before_pos

    while i > 0:
        if i in span_end_to_start:
            i = span_end_to_start[i]
            continue
        if content[i - 1] in ";{}":
            return i - 1
        i -= 1

    return -1


def _classify(
    content: str,
    site_start: int,
    site_end: int,
    spans: List[Tuple[int, int]],
) -> str:
    boundary = _find_statement_boundary(content, spans, site_start)
    prefix = content[boundary + 1:site_start].strip()

    if re.search(r"\breturn\s*$", prefix):
        return "return"

    if re.search(r"(?<![=!<>+\-*/%&|^])=\s*$", prefix):
        return "assignment"

    if re.search(r"(?:\+=|-=|\*=|/=|%=|&=|\|=|\^=|<<=|>>=|>>>=)\s*$", prefix):
        return "assignment"

    if content[site_end:].lstrip().startswith(";"):
        return "statement"

    return "expression"


def find_call_sites(content: str) -> List[CallSite]:
    """
    Find syntactically valid createDragSourceContext invocations.

    Only the exact legacy seven-argument signature is transformed:

        dscp, dgl, dragCursor, dragImage, imageOffset, t, dsl

    The Java 21 API removes only dscp, leaving six arguments.
    """
    spans = _build_lexical_spans(content)
    span_end_to_start = {end: start for start, end in spans}
    sites: List[CallSite] = []

    for match in _CALL_HEAD.finditer(content):
        dot_idx = match.start()

        if _pos_in_any_span(dot_idx, spans):
            continue

        open_paren = content.find("(", dot_idx, match.end())
        if open_paren == -1:
            continue

        receiver_start = _scan_receiver_backward(
            content,
            dot_idx,
            span_end_to_start,
        )
        if receiver_start is None:
            continue

        close_paren = _find_matching_paren(content, open_paren)
        if close_paren is None:
            continue

        args = _split_top_level_arguments(
            content,
            open_paren + 1,
            close_paren,
        )
        if args is None or len(args) != 7:
            # Never guess an overload or malformed call.
            continue

        sites.append(
            CallSite(
                start=receiver_start,
                end=close_paren + 1,
                receiver=content[receiver_start:dot_idx].strip(),
                args=tuple(args),
                kind=_classify(
                    content,
                    receiver_start,
                    close_paren + 1,
                    spans,
                ),
                line_no=content.count("\n", 0, receiver_start) + 1,
            )
        )

    return sites


class DragSourceContextTransformer(BaseTransformer):
    """
    Migrates statement-form legacy createDragSourceContext(...) calls.

    Java 8:
        receiver.createDragSourceContext(
            dscp, dgl, dragCursor, dragImage,
            imageOffset, t, dsl);

    Java 21:
        receiver.createDragSourceContext(
            dgl, dragCursor, dragImage,
            imageOffset, t, dsl);

    The removed API parameter is the DragSourceContextPeer (dscp).  The
    remaining six arguments are preserved in their original order and are
    not rewritten.

    This transformer deliberately does NOT:
      - call startDrag()
      - generate placeholder code
      - throw UnsupportedOperationException
      - add comments/tags
      - generate helper classes
      - mark anything for manual review
    """

    def transform(self, content: str):
        changes: List[str] = []

        # This transformer owns only standalone statement calls.
        sites = [
            site
            for site in find_call_sites(content)
            if site.kind == "statement"
        ]

        # Work backwards so earlier offsets remain valid.
        for site in reversed(sites):
            old_args = site.args
            new_args = ", ".join(old_args[1:])

            # Defensive guard. The discovery routine guarantees six
            # remaining arguments, but keep the replacement fail-safe.
            if len(old_args) != 7 or not new_args.strip():
                continue

            old_call = (
                f"{site.receiver}.{CALL_NAME}"
                f"({', '.join(old_args)})"
            )

            new_call = (
                f"{site.receiver}.{CALL_NAME}"
                f"({new_args})"
            )

            # Replace exactly the invocation expression. The trailing
            # semicolon remains in the original source.
            content = (
                content[:site.start]
                + new_call
                + content[site.end:]
            )

            changes.append(
                f"Line {site.line_no}: migrated "
                f"createDragSourceContext() by removing the obsolete "
                f"DragSourceContextPeer argument."
            )

        return content, changes