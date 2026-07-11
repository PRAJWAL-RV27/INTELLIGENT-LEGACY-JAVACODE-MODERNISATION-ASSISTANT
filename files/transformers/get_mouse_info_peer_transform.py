"""
get_mouse_info_peer_transform.py

Migrates legacy getMouseInfoPeer() usage to public Java 21 AWT APIs.
"""

import re

from .base_transformer import BaseTransformer


class GetMouseInfoPeerTransformer(BaseTransformer):

    _MOUSEINFOPEER_IMPORT = re.compile(
        r'^\s*import\s+java\.awt\.peer\.MouseInfoPeer\s*;\s*$',
        re.MULTILINE,
    )

    _TOOLKIT_IMPORT = re.compile(
        r'^\s*import\s+java\.awt\.Toolkit\s*;\s*$',
        re.MULTILINE,
    )

    _MOUSEINFO_IMPORT = re.compile(
        r'^\s*import\s+java\.awt\.MouseInfo\s*;\s*$',
        re.MULTILINE,
    )

    _POINTERINFO_IMPORT = re.compile(
        r'^\s*import\s+java\.awt\.PointerInfo\s*;\s*$',
        re.MULTILINE,
    )

    _TOOLKIT_DECL = re.compile(
        r'(?m)^(?P<indent>[ \t]*)(?:final\s+)?(?:java\.awt\.)?Toolkit\s+(?P<name>[A-Za-z_]\w*)\s*=\s*Toolkit\.getDefaultToolkit\s*\(\s*\)\s*;\s*$'
    )

    _DECL_PATTERN = re.compile(
        r'(?ms)^(?P<indent>[ \t]*)'
        r'(?P<type>(?:final\s+)?(?:java\.awt\.peer\.MouseInfoPeer|MouseInfoPeer))\s+'
        r'(?P<name>[A-Za-z_]\w*)\s*=\s*'
        r'(?P<rhs>.*?getMouseInfoPeer\s*\(\s*\)\s*;\s*)$'
    )

    _ASSIGN_PATTERN = re.compile(
        r'(?ms)^(?P<indent>[ \t]*)'
        r'(?P<lhs>.+?\S\s*=\s*)'
        r'(?P<alias>[A-Za-z_]\w*)\.fillPointWithCoords\s*\(\s*(?P<arg>.*?)\s*\)\s*;\s*$'
    )

    _MULTILINE_ASSIGN_PATTERN = re.compile(
        r'(?ms)^(?P<indent>[ \t]*)'
        r'(?P<lhs>(?:final\s+)?int\s+[A-Za-z_]\w*\s*=)\s*\n'
        r'(?P<call_indent>[ \t]*)'
        r'(?P<alias>[A-Za-z_]\w*)\.fillPointWithCoords\s*\(\s*(?P<arg>.*?)\s*\)\s*;\s*$'
    )

    _RETURN_PATTERN = re.compile(
        r'(?ms)^(?P<indent>[ \t]*)return\s+'
        r'(?P<alias>[A-Za-z_]\w*)\.fillPointWithCoords\s*\(\s*(?P<arg>.*?)\s*\)\s*;\s*$'
    )

    _MULTILINE_RETURN_PATTERN = re.compile(
        r'(?ms)^(?P<indent>[ \t]*)return\s*\n'
        r'(?P<call_indent>[ \t]*)'
        r'(?P<alias>[A-Za-z_]\w*)\.fillPointWithCoords\s*\(\s*(?P<arg>.*?)\s*\)\s*;\s*$'
    )

    _STATEMENT_PATTERN = re.compile(
        r'(?ms)^(?P<indent>[ \t]*)'
        r'(?P<alias>[A-Za-z_]\w*)\.fillPointWithCoords\s*\(\s*(?P<arg>.*?)\s*\)\s*;\s*$'
    )

    @staticmethod
    def _insert_imports(content: str, imports: list[str]) -> str:
        if not imports:
            return content

        package_match = re.search(r'^\s*package\s+.*?;\s*$', content, re.MULTILINE)
        insert_pos = package_match.end() if package_match else 0
        insertion = '\n'.join(imports)

        if insert_pos:
            return content[:insert_pos] + '\n\n' + insertion + content[insert_pos:]
        return insertion + '\n' + content

    @staticmethod
    def _remove_unused_toolkit(content: str) -> str:
        match = GetMouseInfoPeerTransformer._TOOLKIT_DECL.search(content)
        if not match:
            return content

        name = match.group('name')
        body_without_decl = content[:match.start()] + content[match.end():]
        if re.search(rf'\b{name}\b', body_without_decl):
            return content

        result = body_without_decl
        result = GetMouseInfoPeerTransformer._TOOLKIT_IMPORT.sub('', result)
        return result

    @staticmethod
    def _pointer_block(indent: str, point_expr: str, declare_pointerinfo: bool, screen_index_name: str | None = None) -> str:
        inner = indent + '    '
        lines: list[str] = []

        if declare_pointerinfo:
            lines.append(f'{indent}PointerInfo pointerInfo = MouseInfo.getPointerInfo();')

        if screen_index_name is not None:
            lines.append(f'{indent}int {screen_index_name} = 0;')

        lines.append(f'{indent}if (pointerInfo != null) {{')
        lines.append(f'{inner}{point_expr}.setLocation(pointerInfo.getLocation());')
        lines.append(f'{inner}java.awt.GraphicsDevice device = pointerInfo.getDevice();')
        lines.append(f'{inner}java.awt.GraphicsDevice[] devices =')
        lines.append(f'{inner}    java.awt.GraphicsEnvironment.getLocalGraphicsEnvironment().getScreenDevices();')
        lines.append(f'{inner}for (int i = 0; i < devices.length; i++) {{')
        lines.append(f'{inner}    if (devices[i].equals(device)) {{')
        if screen_index_name is not None:
            lines.append(f'{inner}        {screen_index_name} = i;')
        lines.append(f'{inner}        break;')
        lines.append(f'{inner}    }}')
        lines.append(f'{inner}}}')
        lines.append(f'{indent}}}')
        return '\n'.join(lines)

    def transform(self, content: str) -> tuple[str, list[str]]:
        changes: list[str] = []

        if 'getMouseInfoPeer' not in content and 'MouseInfoPeer' not in content:
            return content, changes

        needs_mouseinfo = False
        needs_pointerinfo = False
        pointerinfo_emitted = False
        result = content

        if self._MOUSEINFOPEER_IMPORT.search(result):
            result = self._MOUSEINFOPEER_IMPORT.sub('', result)
            changes.append('Removed java.awt.peer.MouseInfoPeer import')

        def _replace_decl(match: re.Match) -> str:
            nonlocal needs_mouseinfo, needs_pointerinfo, pointerinfo_emitted
            needs_mouseinfo = True
            needs_pointerinfo = True
            pointerinfo_emitted = True
            changes.append('Replaced MouseInfoPeer declaration with PointerInfo declaration')
            return f"{match.group('indent')}PointerInfo pointerInfo = MouseInfo.getPointerInfo();"

        result = self._DECL_PATTERN.sub(_replace_decl, result)

        def _replace_assign(match: re.Match) -> str:
            nonlocal needs_mouseinfo, needs_pointerinfo, pointerinfo_emitted
            needs_mouseinfo = True
            needs_pointerinfo = True

            indent = match.group('indent')
            lhs = match.group('lhs').rstrip()
            base_indent = indent if indent else re.match(r'[ \t]*', lhs).group(0)
            lhs_text = lhs[len(base_indent):].lstrip() if lhs.startswith(base_indent) else lhs.lstrip()
            arg = match.group('arg').strip()

            if lhs_text.startswith('int '):
                changes.append('Replaced fillPointWithCoords() int assignment with PointerInfo-based device index')
                var_match = re.search(r'(?:final\s+)?int\s+([A-Za-z_]\w*)\s*=', lhs_text)
                target_name = var_match.group(1) if var_match else 'screenIndex'
                block = self._pointer_block(base_indent, arg, not pointerinfo_emitted, target_name)
                pointerinfo_emitted = True
                return block

            changes.append('Replaced fillPointWithCoords() assignment with PointerInfo-based logic')
            if not pointerinfo_emitted:
                pointerinfo_emitted = True
                return '\n'.join([
                    f'{base_indent}PointerInfo pointerInfo = MouseInfo.getPointerInfo();',
                    f'{base_indent}{lhs_text} 0;',
                    f'{base_indent}if (pointerInfo != null) {{',
                    f'{base_indent}    {arg}.setLocation(pointerInfo.getLocation());',
                    f'{base_indent}}}',
                ])

            return '\n'.join([
                f'{base_indent}{lhs_text} 0;',
                f'{base_indent}if (pointerInfo != null) {{',
                f'{base_indent}    {arg}.setLocation(pointerInfo.getLocation());',
                f'{base_indent}}}',
            ])

        result = self._MULTILINE_ASSIGN_PATTERN.sub(_replace_assign, result)
        result = self._ASSIGN_PATTERN.sub(_replace_assign, result)

        def _replace_return(match: re.Match) -> str:
            nonlocal needs_mouseinfo, needs_pointerinfo, pointerinfo_emitted
            needs_mouseinfo = True
            needs_pointerinfo = True
            changes.append('Replaced fillPointWithCoords() return with PointerInfo-based device index')
            block = self._pointer_block(match.group('indent'), 'coordinates', not pointerinfo_emitted, 'screenIndex')
            pointerinfo_emitted = True
            return block + f"\n{match.group('indent')}return screenIndex;"

        result = self._MULTILINE_RETURN_PATTERN.sub(_replace_return, result)
        result = self._RETURN_PATTERN.sub(_replace_return, result)

        def _replace_statement(match: re.Match) -> str:
            nonlocal needs_mouseinfo, needs_pointerinfo, pointerinfo_emitted
            needs_mouseinfo = True
            needs_pointerinfo = True
            changes.append('Replaced fillPointWithCoords() statement with PointerInfo.getLocation()')

            indent = match.group('indent')
            arg = match.group('arg').strip()
            if not pointerinfo_emitted:
                pointerinfo_emitted = True
                return '\n'.join([
                    f'{indent}PointerInfo pointerInfo = MouseInfo.getPointerInfo();',
                    f'{indent}if (pointerInfo != null) {{',
                    f'{indent}    {arg}.setLocation(pointerInfo.getLocation());',
                    f'{indent}}}',
                ])

            return '\n'.join([
                f'{indent}if (pointerInfo != null) {{',
                f'{indent}    {arg}.setLocation(pointerInfo.getLocation());',
                f'{indent}}}',
            ])

        result = self._STATEMENT_PATTERN.sub(_replace_statement, result)

        imports: list[str] = []
        if needs_mouseinfo and not self._MOUSEINFO_IMPORT.search(result):
            imports.append('import java.awt.MouseInfo;')
        if needs_pointerinfo and not self._POINTERINFO_IMPORT.search(result):
            imports.append('import java.awt.PointerInfo;')

        result = self._insert_imports(result, imports)
        result = self._remove_unused_toolkit(result)

        if not re.search(r'\bgetMouseInfoPeer\s*\(', result):
            changes.append('Migrated getMouseInfoPeer() usages to public AWT APIs')

        return result, changes