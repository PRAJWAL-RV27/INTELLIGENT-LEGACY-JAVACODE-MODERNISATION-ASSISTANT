"""
import_cleaner.py — Comment out imports for APIs removed from the JDK.

APIs handled (see config.REMOVED_IMPORTS for the full table)
────────────────────────────────────────────────────────────
  sun.misc.BASE64Encoder/Decoder  →  java.util.Base64  (auto-added)
  javax.xml.bind.*                →  add Maven dep
  javax.xml.ws.*                  →  add Maven dep
  javax.activation.*              →  add Maven dep
  javax.jws.*                     →  add Maven dep
  java.util.jar.Pack200           →  remove usage
  com.sun.*  / sun.*              →  use public APIs

Algorithm
─────────
  1. Split source into lines.
  2. For each `import` line that matches a removed prefix:
       a. Prepend a JAVA21-MIGRATION comment with the reason.
       b. Comment out the original import line.
       c. If a drop-in replacement import exists (e.g. java.util.Base64),
          add it once — only the first time that replacement is needed.
  3. Non-matching lines are passed through unchanged.

Safety guarantee
────────────────
  Commenting out an import of a removed API makes the file compile-safe on
  Java 21.  The developer must update call-sites where the removed type was
  actually used; those are flagged by the compiler after this step.
"""
import re
from .base_transformer import BaseTransformer
from config import REMOVED_IMPORTS


class ImportCleanerTransformer(BaseTransformer):

    def transform(self, content: str) -> tuple[str, list[str]]:
        changes: list[str] = []
        lines = content.split("\n")
        new_lines: list[str] = []

        # Track which replacement imports we have already inserted
        added_replacements: set[str] = set()

        for line in lines:
            stripped = line.strip()
            if stripped.startswith("import javax.xml.bind"):
                new_lines.append(line)
                continue
            if stripped.startswith("import javax.xml.soap"):
                new_lines.append(line)
                continue
            if not stripped.startswith("import "):
                new_lines.append(line)
                continue
            if stripped.startswith("import javax.xml.ws.handler.soap"):
                new_lines.append(line)
                continue
            if "javax.xml.bind" in line:
                return content, []
            # Extract the import path (strip 'import ' and trailing ';')
            import_path = stripped[len("import "):].rstrip(";").strip()
            matched = False

            for prefix, (replacement, message) in REMOVED_IMPORTS.items():
                if (
                    import_path == prefix
                    or import_path.startswith(prefix + ".")
                    or (prefix.endswith(".") and import_path.startswith(prefix))
                ):
                    # Add migration comment
                    new_lines.append(f"// JAVA21-MIGRATION: {message}")
                    # Comment out the original import
                    new_lines.append(f"// {line.rstrip()}")

                    # Auto-insert replacement import (once per replacement)
                    if replacement and replacement not in added_replacements:
                        new_lines.append(f"import {replacement};")
                        added_replacements.add(replacement)

                    changes.append(
                        f"Commented out removed import `{import_path}` "
                        f"({message[:55]}...)"
                    )
                    matched = True
                    break

            if not matched:
                new_lines.append(line)

        result = "\n".join(new_lines)

        # ---- rewrite call sites of sun.misc.BASE64Encoder / BASE64Decoder ----
        if any("BASE64" in c for c in changes):
            result, call_changes = self._rewrite_base64_calls(result)
            changes.extend(call_changes)

        return result, changes

    @staticmethod
    def _rewrite_base64_calls(src: str) -> tuple[str, list[str]]:
        changes: list[str] = []

        # new BASE64Encoder().encode(X)  /  encodeBuffer(X)
        new_src, n = re.subn(
            r'new\s+(?:sun\.misc\.)?BASE64Encoder\s*\(\s*\)\s*\.\s*encode(?:Buffer)?\s*\(',
            'Base64.getEncoder().encodeToString(', src)
        if n:
            changes.append(f"Rewrote {n}x new BASE64Encoder().encode(..) -> Base64.getEncoder().encodeToString(..)")
        src = new_src

        # new BASE64Decoder().decodeBuffer(X)
        new_src, n = re.subn(
            r'new\s+(?:sun\.misc\.)?BASE64Decoder\s*\(\s*\)\s*\.\s*decodeBuffer\s*\(',
            'Base64.getDecoder().decode(', src)
        if n:
            changes.append(f"Rewrote {n}x new BASE64Decoder().decodeBuffer(..) -> Base64.getDecoder().decode(..)")
        src = new_src

        # Variable form:  BASE64Encoder e = new BASE64Encoder();  e.encode(x)
        for cls, meth, repl, label in (
            ("BASE64Encoder", r"encode(?:Buffer)?", "Base64.getEncoder().encodeToString(", "encoder"),
            ("BASE64Decoder", r"decodeBuffer",      "Base64.getDecoder().decode(",         "decoder"),
        ):
            decl = re.compile(
                r'^[ \t]*(?:(?:private|public|protected|static|final|volatile)\s+)*' + cls + r'\s+(\w+)\s*=\s*new\s+' + cls + r'\s*\(\s*\)\s*;[ \t]*\r?\n',
                re.M)
            for m in list(decl.finditer(src)):
                var = m.group(1)
                src = src.replace(m.group(0), "", 1)
                src, k = re.subn(r'\b' + re.escape(var) + r'\s*\.\s*' + meth + r'\s*\(', repl, src)
                changes.append(f"Rewrote BASE64 {label} variable `{var}` ({k} call(s))")

        src = ImportCleanerTransformer._fix_unreachable_ioexception_catch(src, changes)
        return src, changes

    @staticmethod
    def _fix_unreachable_ioexception_catch(src: str, changes: list[str]) -> str:
        """BASE64Decoder.decodeBuffer() threw IOException; Base64.decode() does not.
        A try-block that only called it would now fail to compile with
        'exception IOException is never thrown'. Widen that catch to Exception."""
        io_markers = ("read", "write", "File", "Stream", "Reader", "Writer",
                      "close(", "new IOException", "Files.", "Socket", "URL", "flush")
        pos = 0
        try_re = re.compile(r'\btry\s*\{')
        catch_re = re.compile(r'\s*catch\s*\(\s*(?:java\.io\.)?IOException\s+(\w+)\s*\)')
        while True:
            m = try_re.search(src, pos)
            if not m:
                break
            depth, i = 0, m.end() - 1
            while i < len(src):
                if src[i] == "{":
                    depth += 1
                elif src[i] == "}":
                    depth -= 1
                    if depth == 0:
                        break
                i += 1
            body = src[m.end():i]
            c = catch_re.match(src, i + 1)
            if (c and "Base64.getDecoder().decode(" in body
                    and not any(k in body for k in io_markers)):
                new = f"\n{' ' * 0}".strip("\n") + c.group(0).replace("java.io.IOException", "Exception").replace("IOException", "Exception")
                src = src[:c.start()] + new + src[c.end():]
                changes.append("Widened catch (IOException) to catch (Exception) because Base64.decode() no longer throws IOException")
            pos = m.end()
        return src
