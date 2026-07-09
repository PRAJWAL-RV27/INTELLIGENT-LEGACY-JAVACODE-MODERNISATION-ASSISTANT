import re
from .base_transformer import BaseTransformer


class FinalizeTransformer(BaseTransformer):
    def transform(self, content: str):
        changes = []

        # Regex to match finalize() with optional annotations
        # We match the header only; body is extracted with brace counting.
        header_pattern = re.compile(r'''
            (?:@Deprecated\(.*?\)\s*)?        # Optional @Deprecated
            (?:@SuppressWarnings\(.*?\)\s*)?  # Optional @SuppressWarnings
            \s*(public|protected)\s+void\s+finalize\s*\(\s*\)\s*(?:throws\s+\w[\w.,\s]*)?\{
        ''', re.VERBOSE)

        # Process one match at a time (content shifts on each replacement)
        while True:
            match = re.search(header_pattern, content)
            if not match:
                break

            # Balanced-brace extraction
            brace_start = content.index('{', match.start())
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
            method_start = match.start()

            # CASE 1: EMPTY finalize → REMOVE
            if method_body == "":
                content = content[:method_start] + content[method_end:]
                changes.append("Removed empty finalize() method")
                continue

            # CASE 2: NON-EMPTY → CONVERT
            new_method = f"""
    @Override
    public void close() {{
        {method_body}
    }}
    """
            content = content[:method_start] + new_method + content[method_end:]
            changes.append("Converted finalize() to close()")

            # Add AutoCloseable to the nearest enclosing class
            # Re-search from scratch on updated content
            class_pattern = re.compile(r'class\s+(\w+)([^{]*)\{')
            # Find the class whose '{' is before our inserted method
            new_method_start = method_start  # position hasn't shifted for the class above
            best_cls = None
            for cls in class_pattern.finditer(content):
                if cls.start() < new_method_start:
                    best_cls = cls
                # Stop once we've passed the method position
                if cls.start() > new_method_start:
                    break

            if best_cls is not None:
                class_name = best_cls.group(1)
                class_decl = best_cls.group(0)
                if "AutoCloseable" not in class_decl:
                    new_decl = class_decl.replace(
                        class_name,
                        f"{class_name} implements AutoCloseable",
                        1,
                    )
                    content = content[:best_cls.start()] + new_decl + content[best_cls.end():]
                    changes.append(f"Added AutoCloseable to class {class_name}")

        return content, changes