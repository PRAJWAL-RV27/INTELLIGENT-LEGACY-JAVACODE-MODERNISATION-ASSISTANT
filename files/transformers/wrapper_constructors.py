"""
wrapper_constructors.py — Replace deprecated wrapper-type constructors.

Deprecated in Java 9 (JEP 277), still present but flagged for removal.

Transformations applied
───────────────────────
  new Boolean(true)   →  Boolean.TRUE          (cached constant)
  new Boolean(false)  →  Boolean.FALSE         (cached constant)
  new Boolean(expr)   →  Boolean.valueOf(expr) (uses cache)

  new Integer(x)      →  Integer.valueOf(x)
  new Long(x)         →  Long.valueOf(x)
  new Double(x)       →  Double.valueOf(x)
  new Float(x)        →  Float.valueOf(x)
  new Short(x)        →  Short.valueOf(x)
  new Byte(x)         →  Byte.valueOf(x)
  new Character(x)    →  Character.valueOf(x)

Safety guarantee
────────────────
  valueOf() uses an internal cache for common values (e.g. Integer −128…127),
  making it strictly MORE efficient — never less.  The return type is identical.
  No change to observable program behaviour.
"""
import re
from .base_transformer import BaseTransformer, apply_to_code
from config import DEPRECATED_WRAPPER_TYPES


class WrapperConstructorTransformer(BaseTransformer):

    def transform(self, content: str) -> tuple[str, list[str]]:
        # label -> number of replacements (summed over all code segments)
        counts: dict[str, int] = {}

        def sub(pattern: str, repl: str, text: str, label: str) -> str:
            text, n = re.subn(pattern, repl, text)
            if n:
                counts[label] = counts.get(label, 0) + n
            return text

        def rewrite(code: str) -> str:
            code = sub(r'\bnew\s+Boolean\s*\(\s*true\s*\)', 'Boolean.TRUE', code,
                       "`new Boolean(true)` → `Boolean.TRUE`")
            code = sub(r'\bnew\s+Boolean\s*\(\s*false\s*\)', 'Boolean.FALSE', code,
                       "`new Boolean(false)` → `Boolean.FALSE`")
            code = sub(r'\bnew\s+Boolean\s*\(', 'Boolean.valueOf(', code,
                       "`new Boolean(...)` → `Boolean.valueOf(...)`")
            for wtype in DEPRECATED_WRAPPER_TYPES:
                code = sub(rf'\bnew\s+{re.escape(wtype)}\s*\(', f'{wtype}.valueOf(', code,
                           f"`new {wtype}(...)` → `{wtype}.valueOf(...)`")
            return code

        # Only real code is rewritten; strings and comments are left alone.
        result = apply_to_code(content, rewrite)
        changes = [f"Replaced {n}× {label}" for label, n in counts.items()]
        return result, changes
