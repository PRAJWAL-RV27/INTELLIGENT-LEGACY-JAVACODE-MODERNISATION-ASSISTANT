import re
from .base_transformer import BaseTransformer


class FinalizeTransformer(BaseTransformer):
    SAFE_FINALIZER_TYPES = {"Deflater", "Inflater", "ZipFile", "ICC_Profile"}

    def transform(self, content: str):
        changes = []

        header_pattern = re.compile(r'''
            (?:@Deprecated\(.*?\)\s*)?
            (?:@SuppressWarnings\(.*?\)\s*)?
            \s*(public|protected)\s+void\s+finalize\s*\(\s*\)\s*(?:throws\s+\w[\w.,\s]*)?\{
        ''', re.VERBOSE)

        search_start = 0
        while True:
            match = re.search(header_pattern, content[search_start:])
            if not match:
                break

            abs_start = search_start + match.start()
            nearest_class = self._nearest_class_name_before(content, abs_start)
            if nearest_class not in self.SAFE_FINALIZER_TYPES:
                search_start = abs_start + match.end() - match.start()
                continue

            brace_start = content.index('{', abs_start)
            depth, i = 0, brace_start
            while i < len(content):
                if content[i] == '{':
                    depth += 1
                elif content[i] == '}':
                    depth -= 1
                    if depth == 0:
                        break
                i += 1
            method_end = i + 1
            method_body = content[brace_start + 1:i].strip()

            if method_body == "":
                content = content[:abs_start] + content[method_end:]
                changes.append("Removed empty finalize() method")
                search_start = abs_start
                continue

            new_method = f"""
    @Override
    public void close() {{
        {method_body}
    }}
    """
            content = content[:abs_start] + new_method + content[method_end:]
            changes.append("Converted finalize() to close()")
            search_start = abs_start

            class_pattern = re.compile(r'class\s+(\w+)([^{]*)\{')
            best_cls = None
            for cls in class_pattern.finditer(content):
                if cls.start() < abs_start:
                    best_cls = cls
                if cls.start() > abs_start:
                    break

            if best_cls is not None:
                class_name = best_cls.group(1)
                class_decl = best_cls.group(0)
                if "AutoCloseable" not in class_decl and class_name in self.SAFE_FINALIZER_TYPES:
                    new_decl = class_decl.replace(
                        class_name,
                        f"{class_name} implements AutoCloseable",
                        1,
                    )
                    content = content[:best_cls.start()] + new_decl + content[best_cls.end():]
                    changes.append(f"Added AutoCloseable to class {class_name}")

        return content, changes

    def _nearest_class_name_before(self, content: str, index: int):
        class_pattern = re.compile(r'class\s+(\w+)\b')
        best_name = None
        for match in class_pattern.finditer(content):
            if match.start() < index:
                best_name = match.group(1)
            else:
                break
        return best_name