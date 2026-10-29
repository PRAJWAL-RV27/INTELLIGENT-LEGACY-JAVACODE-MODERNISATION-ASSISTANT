import re


class SequentialStreamForEachTransformer:
    """
    Converts simple sequential Stream.forEach() calls into
    enhanced for-loops.

    Example:

        list.stream().forEach(x -> process(x));

    becomes:

        for (var x : list) {
            process(x);
        }

    Only simple, single-expression lambdas are transformed.
    Parallel streams and complex/block lambdas are ignored.
    """

    NAME = "Sequential stream().forEach() -> enhanced for-loop"

    def transform(self, content: str):
        changes = []

        pattern = re.compile(
            r"""
            (?P<collection>
                \b[A-Za-z_$][\w$]*
                (?:\.[A-Za-z_$][\w$]*)*
            )
            \.stream\(\)
            \.forEach\(
                \s*
                (?P<variable>[A-Za-z_$][\w$]*)
                \s*->\s*
                (?P<body>
                    [^;{}()\n]+
                    (?:\([^;{}()\n]*\))?
                )
            \)
            \s*;
            """,
            re.VERBOSE,
        )

        def replace(match):
            collection = match.group("collection")
            variable = match.group("variable")
            body = match.group("body").strip()

            # Safety checks
            if "->" in body:
                return match.group(0)

            if ".stream()" in body:
                return match.group(0)

            if ".parallelStream()" in body:
                return match.group(0)

            changes.append(
                f"Replaced {collection}.stream().forEach("
                f"{variable} -> {body}) with enhanced for-loop"
            )

            return (
                f"for (var {variable} : {collection}) {{\n"
                f"    {body};\n"
                f"}}"
            )

        transformed = pattern.sub(replace, content)

        return transformed, changes