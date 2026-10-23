"""
deprecated_methods.py — Comment out method calls that were REMOVED from the JDK.

Removed APIs handled
────────────────────
  Thread.stop(Throwable)          Removed Java 11  — use interrupt()
  Runtime.runFinalizersOnExit()   Removed Java 11  — remove finalizer reliance
  System.runFinalizersOnExit()    Removed Java 11  — remove finalizer reliance

Why comment-out instead of auto-rewrite?
─────────────────────────────────────────
  These APIs require a design change (e.g. cooperative cancellation patterns).
  Auto-rewriting would silently change program logic.  Instead we preserve the
  original statement as a comment so the developer sees exactly what must be
  addressed, with a clear TODO explaining the required change.

Safety guarantee
────────────────
  The commented-out line is never executed, so no behaviour change can occur
  from the transformation itself.  A TODO comment is added directly above it.
"""
import re
from .base_transformer import BaseTransformer


# Each entry: (compiled_regex, short_label, todo_message)
_REMOVED: list[tuple[re.Pattern, str, str]] = [
    (
        re.compile(
            r'(?P<indent>[ \t]*)'
            r'(?P<stmt>'
            r'Runtime\s*\.\s*(?:getRuntime\s*\(\s*\)\s*\.\s*)?'
            r'runFinalizersOnExit\s*\([^;]*\)\s*;)',
            re.MULTILINE,
        ),
        "Runtime.runFinalizersOnExit()",
        "Runtime.runFinalizersOnExit() was REMOVED in Java 11. "
        "Do not rely on finalizers; remove this call.",
    ),
    (
        re.compile(
            r'(?P<indent>[ \t]*)'
            r'(?P<stmt>System\s*\.\s*runFinalizersOnExit\s*\([^;]*\)\s*;)',
            re.MULTILINE,
        ),
        "System.runFinalizersOnExit()",
        "System.runFinalizersOnExit() was REMOVED in Java 11. "
        "Do not rely on finalizers; remove this call.",
    ),
]


_STOP_START = re.compile(
    r'(?P<indent>^[ \t]*)(?P<recv>(?:\w[\w.]*\s*\.\s*)?)stop\s*\(', re.MULTILINE)

_STOP_TODO = ("Thread.stop(Throwable) was REMOVED in Java 11. "
              "Use Thread.interrupt() with a cooperative cancellation flag.")


def _find_stmt_end(src: str, open_idx: int):
    """open_idx points at '('. Return (index just after matching ')', has_arg)
    or None. Skips string/char literals so quotes/parens inside them are ignored."""
    depth, i, n = 0, open_idx, len(src)
    has_arg = False
    while i < n:
        ch = src[i]
        if ch in "\"'":
            q = ch; i += 1
            while i < n and src[i] != q:
                i += 2 if src[i] == "\\" else 1
            has_arg = True
        elif ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0:
                return i + 1, has_arg
        elif not ch.isspace() and depth >= 1:
            has_arg = True
        i += 1
    return None


_THROWABLE_NEW = re.compile(r'^\s*new\s+[\w.]*(?:Exception|Error|Throwable|ThreadDeath)\b')


def _looks_like_thread_stop(src: str, m, arg: str) -> bool:
    """True only for Thread.stop(Throwable): the argument is a new Throwable,
    or a variable declared as a Throwable, or the receiver is declared as a Thread.
    Own methods like  stopwatch.stop("label")  are NOT touched."""
    arg = arg.strip()
    if _THROWABLE_NEW.match(arg):
        return True
    if re.fullmatch(r'\w+', arg) and re.search(
            r'\b(?:Throwable|\w*Exception|\w*Error)\s+' + re.escape(arg) + r'\b', src):
        return True
    recv = m.group("recv").replace(".", "").strip()
    if recv and re.search(r'\b(?:\w*Thread)\s+' + re.escape(recv) + r'\b', src):
        return True
    return False


def _comment_out_thread_stop(src: str):
    """Comment out `x.stop(<non-empty arg>);` with balanced parentheses."""
    out, pos, count = [], 0, 0
    for m in _STOP_START.finditer(src):
        if m.start() < pos:
            continue
        found = _find_stmt_end(src, m.end() - 1)
        if not found:
            continue
        end, has_arg = found
        tail = re.match(r'\s*;', src[end:])
        if not has_arg or not tail:
            continue
        stmt_end = end + tail.end()
        indent = m.group("indent")
        if not _looks_like_thread_stop(src, m, src[m.end():end - 1]):
            continue
        stmt = src[m.start() + len(indent):stmt_end]
        stmt_commented = stmt.replace("\n", "\n" + indent + "// ")
        out.append(src[pos:m.start()])
        out.append(f"{indent}// TODO(Java21-migration): {_STOP_TODO}\n"
                   f"{indent}// REMOVED: {stmt_commented}")
        pos = stmt_end
        count += 1
    out.append(src[pos:])
    return "".join(out), count


class DeprecatedMethodsTransformer(BaseTransformer):

    def transform(self, content: str) -> tuple[str, list[str]]:
        changes: list[str] = []
        result, n = _comment_out_thread_stop(content)
        if n:
            changes.append(f"Commented out {n}× removed call `Thread.stop(Throwable)` — see TODO in code")

        for pattern, label, todo in _REMOVED:
            def _replace(m: re.Match, _todo: str = todo) -> str:
                indent = m.group("indent")
                stmt   = m.group("stmt")
                return (
                    f"{indent}// TODO(Java21-migration): {_todo}\n"
                    f"{indent}// REMOVED: {stmt}"
                )

            new_result, n = pattern.subn(_replace, result)
            if n:
                changes.append(
                    f"Commented out {n}× removed call `{label}` — see TODO in code"
                )
                result = new_result

        return result, changes
