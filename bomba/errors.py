"""Error types used by every stage of bomba (lexer, parser, interpreter)."""


class BombaError(Exception):
    """An error with an optional source position.

    ``kind`` is the bomba-level error name (``SyntaxError``, ``TypeError`` ...).
    The position is attached lazily: runtime code raises errors without a
    position and the interpreter fills in the innermost node it was evaluating.
    """

    def __init__(self, kind, message, line=None, col=None):
        super().__init__(message)
        self.kind = kind
        self.message = message
        self.line = line
        self.col = col
        self.filename = None
        self.source = None
        # True when a syntax error was caused by the input ending too early.
        # The REPL uses this to ask for another line instead of failing.
        self.incomplete = False

    def attach(self, line=None, col=None, filename=None, source=None):
        if self.line is None and line is not None:
            self.line, self.col = line, col
        if self.filename is None and filename is not None:
            self.filename, self.source = filename, source
        return self

    def format(self):
        """Human-readable report with the offending line and a caret."""
        out = []
        if self.line is not None:
            where = self.filename or "<input>"
            out.append(f'  File "{where}", line {self.line}, column {self.col}')
            if self.source:
                lines = self.source.splitlines()
                if 0 < self.line <= len(lines):
                    text = lines[self.line - 1]
                    stripped = text.lstrip()
                    indent = len(text) - len(stripped)
                    out.append("    " + stripped)
                    out.append("    " + " " * max(0, (self.col or 1) - 1 - indent) + "^")
        out.append(f"{self.kind}: {self.message}")
        return "\n".join(out)

    def __str__(self):
        return f"{self.kind}: {self.message}"


class BombaThrow(BombaError):
    """A value thrown with ``throw`` that nobody caught (yet)."""

    def __init__(self, value, message):
        super().__init__("Uncaught", message)
        self.value = value


def syntax_error(message, token, incomplete=False):
    err = BombaError("SyntaxError", message, token.line, token.col)
    err.incomplete = incomplete
    return err
