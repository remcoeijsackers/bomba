"""Turns bomba source text into a list of tokens."""

from .errors import BombaError

KEYWORDS = {
    "let", "fn", "return", "if", "elif", "else", "while", "for", "in",
    "break", "continue", "true", "false", "nil", "and", "or", "not",
    "try", "catch", "throw", "import",
}

# Longest operators first so "==" wins over "=".
OPERATORS = [
    "//=", "**", "//", "==", "!=", "<=", ">=", "+=", "-=", "*=", "/=", "%=", "=>",
    "+", "-", "*", "/", "%", "<", ">", "=", "(", ")", "[", "]", "{", "}",
    ",", ":", ".", ";",
]

OPENERS = {"(": ")", "[": "]", "{": "}"}


class Token:
    __slots__ = ("type", "value", "line", "col")

    def __init__(self, type, value, line, col):
        self.type = type    # NUMBER STRING IDENT KEYWORD OP NEWLINE EOF
        self.value = value
        self.line = line
        self.col = col

    def __repr__(self):
        return f"Token({self.type}, {self.value!r}, {self.line}:{self.col})"


ESCAPES = {"n": "\n", "t": "\t", "r": "\r", "0": "\0", "\\": "\\", '"': '"', "'": "'", "{": "{", "}": "}"}


class Lexer:
    def __init__(self, source, line=1, col=1):
        self.src = source
        self.pos = 0
        self.line = line
        self.col = col
        self.tokens = []
        # Stack of open brackets. Newlines only end statements at the top
        # level or directly inside a { } block, never inside ( ) or [ ].
        self.brackets = []

    def error(self, message, line=None, col=None):
        return BombaError("SyntaxError", message, line or self.line, col or self.col)

    def advance(self, n=1):
        for _ in range(n):
            ch = self.src[self.pos]
            self.pos += 1
            if ch == "\n":
                self.line += 1
                self.col = 1
            else:
                self.col += 1

    def peek(self, k=0):
        i = self.pos + k
        return self.src[i] if i < len(self.src) else ""

    def add(self, type, value, line, col):
        self.tokens.append(Token(type, value, line, col))

    def newline_matters(self):
        return not self.brackets or self.brackets[-1] == "{"

    def tokenize(self):
        while self.pos < len(self.src):
            ch = self.peek()
            if ch in " \t\r":
                self.advance()
            elif ch == "#":
                while self.pos < len(self.src) and self.peek() != "\n":
                    self.advance()
            elif ch == "\n":
                line, col = self.line, self.col
                self.advance()
                if self.newline_matters() and self.tokens and self.tokens[-1].type != "NEWLINE":
                    self.add("NEWLINE", "\n", line, col)
            elif ch == "\\" and self.peek(1) == "\n":
                self.advance(2)  # explicit line continuation
            elif ch.isdigit():
                self.number()
            elif ch.isalpha() or ch == "_":
                self.identifier()
            elif ch in "\"'":
                self.string(ch)
            else:
                self.operator()
        if self.tokens and self.tokens[-1].type != "NEWLINE" and self.newline_matters():
            self.add("NEWLINE", "\n", self.line, self.col)
        self.add("EOF", None, self.line, self.col)
        return self.tokens

    def number(self):
        line, col, start = self.line, self.col, self.pos
        while self.peek().isdigit() or self.peek() == "_":
            self.advance()
        is_float = False
        if self.peek() == "." and self.peek(1).isdigit():
            is_float = True
            self.advance()
            while self.peek().isdigit() or self.peek() == "_":
                self.advance()
        if self.peek() in ("e", "E") and (self.peek(1).isdigit() or (self.peek(1) in "+-" and self.peek(2).isdigit())):
            is_float = True
            self.advance(2)
            while self.peek().isdigit():
                self.advance()
        text = self.src[start:self.pos].replace("_", "")
        self.add("NUMBER", float(text) if is_float else int(text), line, col)

    def identifier(self):
        line, col, start = self.line, self.col, self.pos
        while self.peek().isalnum() or self.peek() == "_":
            self.advance()
        word = self.src[start:self.pos]
        self.add("KEYWORD" if word in KEYWORDS else "IDENT", word, line, col)

    def string(self, quote):
        """Strings become a list of parts.

        Each part is either ``str`` (literal text) or a tuple
        ``(source, line, col)`` for an ``{expression}`` to interpolate.
        Only double-quoted strings interpolate; single-quoted ones are literal.
        """
        line, col = self.line, self.col
        self.advance()
        parts, buf = [], []
        interpolate = quote == '"'
        while True:
            ch = self.peek()
            if ch == "" or ch == "\n":
                raise self.error("unterminated string", line, col)
            if ch == quote:
                self.advance()
                break
            if ch == "\\":
                esc = self.peek(1)
                if esc not in ESCAPES:
                    raise self.error(f"unknown escape sequence '\\{esc}'")
                buf.append(ESCAPES[esc])
                self.advance(2)
            elif interpolate and ch == "{":
                if self.peek(1) == "{":
                    buf.append("{")
                    self.advance(2)
                    continue
                if buf:
                    parts.append("".join(buf))
                    buf = []
                self.advance()
                eline, ecol, start, depth = self.line, self.col, self.pos, 1
                while True:
                    c = self.peek()
                    if c == "" or c == "\n":
                        raise self.error("unterminated '{' in string", eline, ecol - 1)
                    if c in "\"'":
                        # skip a nested string literal inside the expression
                        q = c
                        self.advance()
                        while self.peek() not in (q, "", "\n"):
                            if self.peek() == "\\":
                                self.advance()
                            self.advance()
                        if self.peek() == q:
                            self.advance()
                        continue
                    if c == "{":
                        depth += 1
                    elif c == "}":
                        depth -= 1
                        if depth == 0:
                            break
                    self.advance()
                expr = self.src[start:self.pos]
                if not expr.strip():
                    raise self.error("empty {} in string", eline, ecol - 1)
                parts.append((expr, eline, ecol))
                self.advance()  # closing }
            elif interpolate and ch == "}" and self.peek(1) == "}":
                buf.append("}")
                self.advance(2)
            else:
                buf.append(ch)
                self.advance()
        if buf or not parts:
            parts.append("".join(buf))
        self.add("STRING", parts, line, col)

    def operator(self):
        line, col = self.line, self.col
        for op in OPERATORS:
            if self.src.startswith(op, self.pos):
                self.advance(len(op))
                if op in OPENERS:
                    self.brackets.append(op)
                elif op in (")", "]", "}") and self.brackets and OPENERS[self.brackets[-1]] == op:
                    self.brackets.pop()
                self.add("OP", op, line, col)
                return
        raise self.error(f"unexpected character {self.peek()!r}")


def tokenize(source, line=1, col=1):
    return Lexer(source, line, col).tokenize()
