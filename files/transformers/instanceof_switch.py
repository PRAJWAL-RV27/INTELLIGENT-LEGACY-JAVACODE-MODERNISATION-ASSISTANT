"""
instanceof_switch.py — JEP 441 (Java 21): Pattern Matching for switch.

Converts multi-branch if/else-if instanceof chains into switch expressions.

Handles TWO forms of instanceof branches:

  Form A — with pattern variable (already has Java 16 pattern matching):
    if (obj instanceof Integer i) { return i * 2; }

  Form B — without pattern variable (old style with cast inside):
    if (obj instanceof Integer) { return (Integer) obj * 2; }

For Form B, we auto-generate a pattern variable name from the type name
(lowercase first letter) so the switch case can use it.

Safety rules
────────────
  1. All branches check the SAME variable (simple identifier).
  2. At least 2 instanceof branches required.
  3. Each branch body: EXACTLY ONE statement (return expr; or expr;).
  4. All branches consistently return-based or expression-based.
"""
import re
from .base_transformer import BaseTransformer


def _extract_block(source: str, open_pos: int) -> tuple[str, int]:
    depth, i = 0, open_pos
    while i < len(source):
        if   source[i] == '{': depth += 1
        elif source[i] == '}':
            depth -= 1
            if depth == 0:
                return source[open_pos + 1 : i], i + 1
        i += 1
    return source[open_pos + 1:], len(source)


def _single_stmt(block: str) -> str | None:
    stripped = block.strip()
    if '{' in stripped or '}' in stripped:
        return None
    parts = [p.strip() for p in stripped.split(';') if p.strip()]
    return parts[0] if len(parts) == 1 else None


def _is_return(stmt: str) -> tuple[bool, str]:
    m = re.match(r'^return\s+(.+)$', stmt, re.DOTALL)
    return (True, m.group(1).strip()) if m else (False, stmt)


def _indentation(source: str, pos: int) -> str:
    line_start = source.rfind('\n', 0, pos) + 1
    indent = []
    for ch in source[line_start:pos]:
        if ch in (' ', '\t'):
            indent.append(ch)
        else:
            break
    return ''.join(indent)


def _make_pvar(type_name: str) -> str:
    """Generate a safe pattern variable name from a type name."""
    return type_name[0].lower() + type_name[1:] if type_name else 'v'


# Form A: if (var instanceof Type pvar) {
_IF_INST_WITH_VAR = re.compile(
    r'\bif\s*\(\s*'
    r'(?P<var>\w+)\s+instanceof\s+'
    r'(?P<type>\w+(?:\.\w+)*)\s+'
    r'(?P<pvar>\w+)'
    r'\s*\)\s*\{',
    re.MULTILINE,
)

# Form B: if (var instanceof Type) {   — no pattern variable
_IF_INST_NO_VAR = re.compile(
    r'\bif\s*\(\s*'
    r'(?P<var>\w+)\s+instanceof\s+'
    r'(?P<type>\w+(?:\.\w+)*)'
    r'\s*\)\s*\{',
    re.MULTILINE,
)

# else-if variants
_ELSEIF_WITH_VAR = re.compile(
    r'\}\s*else\s+if\s*\(\s*'
    r'(?P<var>\w+)\s+instanceof\s+'
    r'(?P<type>\w+(?:\.\w+)*)\s+'
    r'(?P<pvar>\w+)'
    r'\s*\)\s*\{',
    re.MULTILINE,
)

_ELSEIF_NO_VAR = re.compile(
    r'\}\s*else\s+if\s*\(\s*'
    r'(?P<var>\w+)\s+instanceof\s+'
    r'(?P<type>\w+(?:\.\w+)*)'
    r'\s*\)\s*\{',
    re.MULTILINE,
)

_ELSE_RE = re.compile(r'\}\s*else\s*\{', re.MULTILINE)


def _match_if_inst(source: str, pos: int):
    """
    Try to match an if-instanceof at `pos`, preferring the with-pvar form.
    Returns (match, has_pvar) or (None, False).
    """
    m_with = _IF_INST_WITH_VAR.search(source, pos)
    m_without = _IF_INST_NO_VAR.search(source, pos)

    # Pick the earliest match; if tied, prefer with-pvar
    if m_with is None and m_without is None:
        return None, False
    if m_with is None:
        return m_without, False
    if m_without is None:
        return m_with, True
    if m_with.start() <= m_without.start():
        return m_with, True
    return m_without, False


def _match_elseif_inst(source: str, pos: int):
    """Try to match an else-if-instanceof at `pos`."""
    m_with = _ELSEIF_WITH_VAR.match(source, pos)
    m_without = _ELSEIF_NO_VAR.match(source, pos)
    if m_with:
        return m_with, True
    if m_without:
        return m_without, False
    return None, False


class InstanceofSwitchTransformer(BaseTransformer):

    def transform(self, content: str) -> tuple[str, list[str]]:
        changes: list[str] = []
        result  = content
        processed_ends: list[int] = []
        scan_pos = 0

        while True:
            m, has_pvar = _match_if_inst(content, scan_pos)
            if not m:
                break

            if any(m.start() < end for end in processed_ends):
                scan_pos = m.end()
                continue

            chain_var = m.group('var')
            replacement, orig_end, n_branches = self._try_convert(content, m, has_pvar, chain_var)

            if replacement is None:
                scan_pos = m.end()
                continue

            offset = len(result) - len(content)
            adj_s  = m.start() + offset
            adj_e  = orig_end  + offset
            result = result[:adj_s] + replacement + result[adj_e:]

            processed_ends.append(orig_end)
            scan_pos = orig_end
            changes.append(
                f"Converted {n_branches}-branch instanceof if/else chain on "
                f"`{chain_var}` -> switch expression (JEP 441, Java 21)"
            )

        return result, changes

    def _try_convert(
        self,
        source: str,
        first_match: re.Match,
        first_has_pvar: bool,
        chain_var: str,
    ) -> tuple[str | None, int, int]:
        branches: list[tuple[str, str, str]] = []  # (type, pvar, expr)
        default: str | None = None
        is_ret: bool | None = None

        brace_open = source.index('{', first_match.end() - 1)
        body, pos  = _extract_block(source, brace_open)
        stmt       = _single_stmt(body)
        if stmt is None:
            return None, 0, 0

        type_name = first_match.group('type')
        if first_has_pvar:
            pvar = first_match.group('pvar')
        else:
            # Auto-generate pvar; substitute casts in stmt
            pvar = _make_pvar(type_name)
            stmt = _substitute_cast(stmt, type_name, pvar)

        ret, expr = _is_return(stmt)
        is_ret = ret
        branches.append((type_name, pvar, expr))

        while True:
            m2, has_pvar2 = _match_elseif_inst(source, pos - 1)
            if m2 and m2.group('var') == chain_var:
                brace_open  = source.index('{', m2.end() - 1)
                body, pos   = _extract_block(source, brace_open)
                stmt2       = _single_stmt(body)
                if stmt2 is None:
                    return None, 0, 0

                type2 = m2.group('type')
                if has_pvar2:
                    pvar2 = m2.group('pvar')
                else:
                    pvar2 = _make_pvar(type2)
                    stmt2 = _substitute_cast(stmt2, type2, pvar2)

                ret2, expr2 = _is_return(stmt2)
                if ret2 != is_ret:
                    return None, 0, 0
                branches.append((type2, pvar2, expr2))
                continue

            m3 = _ELSE_RE.match(source, pos - 1)
            if m3:
                brace_open  = source.index('{', m3.end() - 1)
                body, pos   = _extract_block(source, brace_open)
                stmt3       = _single_stmt(body)
                if stmt3 is None:
                    return None, 0, 0
                ret3, expr3 = _is_return(stmt3)
                if ret3 != is_ret:
                    return None, 0, 0
                default = expr3
            break

        if len(branches) < 2:
            return None, 0, 0

        indent = _indentation(source, first_match.start())
        inner  = indent + '    '
        prefix = 'return ' if is_ret else ''

        max_w = max(len(f'case {t} {v}') for t, v, _ in branches)
        if default is not None:
            max_w = max(max_w, len('default'))

        lines = [f'{prefix}switch ({chain_var}) {{']
        for typ, pvar, expr in branches:
            lbl = f'case {typ} {pvar}'
            pad = ' ' * (max_w - len(lbl))
            lines.append(f'{inner}{lbl}{pad} -> {expr};')
        if default is not None:
            pad = ' ' * (max_w - len('default'))
            lines.append(f'{inner}default{pad} -> {default};')
        lines.append(f'{indent}}};')

        return '\n'.join(lines), pos, len(branches)


def _substitute_cast(stmt: str, type_name: str, pvar: str) -> str:
    """
    In a statement that uses (TypeName)obj casts, replace the cast expression
    with the pattern variable so the switch arm reads naturally.

    Example:
      stmt      = "System.out.println((Integer)obj)"
      type_name = "Integer"
      pvar      = "integer"
      result    = "System.out.println(integer)"
    """
    # Replace (TypeName) castTarget with pvar
    cast_pattern = re.compile(
        r'\(\s*' + re.escape(type_name) + r'\s*\)\s*(\w+)'
    )
    return cast_pattern.sub(pvar, stmt)