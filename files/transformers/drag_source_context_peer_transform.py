import re
from dataclasses import dataclass
from typing import List, Optional, Tuple

from .base_transformer import BaseTransformer


CALL_NAME = "createDragSourceContext"

_CALL_HEAD = re.compile(
    r"\." + re.escape(CALL_NAME) + r"\s*\("
)

_JAVA_KEYWORDS_INVALID_AS_RECEIVER = {
    "return",
    "new",
    "throw",
    "else",
    "if",
    "while",
    "for",
    "do",
    "case",
    "yield",
    "assert",
}


@dataclass(frozen=True)
class CallSite:
    start: int
    end: int
    receiver: str
    args: Tuple[str, ...]
    line_no: int


# ---------------------------------------------------------------------------
# Lexical helpers
# ---------------------------------------------------------------------------

def _build_lexical_spans(content: str) -> List[Tuple[int, int]]:
    """
    Return spans occupied by Java string/character literals and comments.

    Those spans are ignored while locating Java syntax.  Text blocks are also
    handled so that Java 15+ sources containing 
    """ 
    """ do not confuse the
    transformer.
    """
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

        # String / character literal
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

        # Line comment
        if c == "/" and i + 1 < n and content[i + 1] == "/":
            start = i
            newline = content.find("\n", i + 2)
            i = n if newline == -1 else newline
            spans.append((start, i))
            continue

        # Block comment
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
    """
    Find the ')' matching the '(' at open_idx.

    Comments, strings, character literals, and text blocks are ignored.
    """
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

        i += 1

    return None


def _split_top_level_arguments(
    content: str,
    start: int,
    end: int,
) -> Optional[List[str]]:
    """
    Split a Java argument list on commas at nesting depth zero.

    Returns None for malformed/unbalanced argument syntax.
    """
    args: List[str] = []
    arg_start = start

    paren = 0
    bracket = 0
    brace = 0

    i = start
    n = end

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
            newline = content.find("\n", i + 2, n)
            i = n if newline == -1 else newline
            continue

        if c == "/" and i + 1 < n and content[i + 1] == "*":
            close = content.find("*/", i + 2, n)
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
            args.append(content[arg_start:i].strip())
            arg_start = i + 1

        i += 1

    if paren != 0 or bracket != 0 or brace != 0:
        return None

    tail = content[arg_start:end].strip()

    # A trailing comma is not valid for a Java method invocation.
    if not tail:
        if not args:
            return []
        return None

    args.append(tail)
    return args


# ---------------------------------------------------------------------------
# Receiver detection
# ---------------------------------------------------------------------------

def _scan_receiver_backward(
    content: str,
    dot_idx: int,
    span_end_to_start: dict,
) -> Optional[int]:
    """
    Conservatively locate the beginning of the expression immediately before
    '.createDragSourceContext('.

    Examples:
        obj
        this.obj
        foo.bar
        arr[i]
        getFoo()
        getFoo().getBar()
        map.get(key).value

    The scanner deliberately rejects casts and Java keywords as receivers.
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
    receiver_text = content[start:dot_idx].strip()

    if not receiver_text:
        return None

    if receiver_text in _JAVA_KEYWORDS_INVALID_AS_RECEIVER:
        return None

    # A cast receiver needs type-aware parsing and is intentionally excluded.
    if receiver_text.startswith("("):
        return None

    return start


# ---------------------------------------------------------------------------
# Call-site discovery
# ---------------------------------------------------------------------------

def find_call_sites(content: str) -> List[CallSite]:
    spans = _build_lexical_spans(content)

    span_end_to_start = {
        end: start
        for start, end in spans
    }

    sites: List[CallSite] = []

    for match in _CALL_HEAD.finditer(content):
        dot_idx = match.start()

        if _pos_in_any_span(dot_idx, spans):
            continue

        open_paren = content.find("(", dot_idx, match.end())

        if open_paren == -1:
            continue

        recv_start = _scan_receiver_backward(
            content,
            dot_idx,
            span_end_to_start,
        )

        if recv_start is None:
            continue

        close_paren = _find_matching_paren(
            content,
            open_paren,
        )

        if close_paren is None:
            continue

        args = _split_top_level_arguments(
            content,
            open_paren + 1,
            close_paren,
        )

        if args is None:
            continue

        # The removed Java 8 API had exactly seven parameters:
        #
        #   dscp, dgl, dragCursor, dragImage, imageOffset, t, dsl
        #
        # Java 21's replacement has six parameters and no dscp:
        #
        #   dgl, dragCursor, dragImage, imageOffset, t, dsl
        #
        # Only transform the exact seven-argument shape.  This prevents the
        # transformer from guessing about unrelated overloads.
        if len(args) != 7:
            continue

        sites.append(
            CallSite(
                start=recv_start,
                end=close_paren + 1,
                receiver=content[recv_start:dot_idx].strip(),
                args=tuple(args),
                line_no=content.count("\n", 0, recv_start) + 1,
            )
        )

    return sites


# ---------------------------------------------------------------------------
# Transformer
# ---------------------------------------------------------------------------

class DragSourceContextPeerTransformer(BaseTransformer):
    """
    Migrates the Java 8 DragSource.createDragSourceContext(...) invocation
    whose first parameter was DragSourceContextPeer.

    Java 8:
        receiver.createDragSourceContext(
            dscp, dgl, dragCursor, dragImage,
            imageOffset, transferable, dsl);

    Java 21:
        receiver.createDragSourceContext(
            dgl, dragCursor, dragImage,
            imageOffset, transferable, dsl);

    The API change is a direct signature change: the DragSourceContextPeer
    parameter was removed.  Therefore the semantics of the call are preserved
    by removing only that obsolete first argument and retaining every other
    expression exactly as written.

    This transformer handles expression contexts as well as statement
    contexts.  It never generates a placeholder, fail-fast helper, or
    manual-review marker.
    """

    def __init__(self):
        super().__init__()

    def transform(self, content: str):
        changes: List[str] = []

        sites = find_call_sites(content)

        if not sites:
            return content, changes

        # Reverse order prevents offset invalidation.
        for site in reversed(sites):
            # The first parameter is the removed DragSourceContextPeer.
            #
            # Important: do NOT evaluate or duplicate any other expression.
            # The remaining six arguments are copied byte-for-byte after
            # stripping only the surrounding argument-list whitespace.
            new_args = ", ".join(site.args[1:])

            old_call = (
                f"{site.receiver}.{CALL_NAME}"
                f"({', '.join(site.args)})"
            )

            new_call = (
                f"{site.receiver}.{CALL_NAME}"
                f"({new_args})"
            )

            # Defensive sanity check: never replace an empty/malformed call.
            if not new_args.strip():
                continue

            content = (
                content[:site.start]
                + new_call
                + content[site.end:]
            )

            changes.append(
                f"Line {site.line_no}: removed the obsolete "
                f"DragSourceContextPeer argument from "
                f"createDragSourceContext() while preserving the "
                f"remaining six arguments."
            )

        return content, changes