"""Recursive-descent parser: tokens in, syntax tree out.

Grammar (lowest to highest precedence for expressions):

    program    := statement*
    statement  := let | fn-def | if | while | for | try | throw | return
                | break | continue | import | expr [assign-op expr]
    expression := or
    or         := and ("or" and)*
    and        := not ("and" not)*
    not        := "not" not | comparison
    comparison := sum (("==" | "!=" | "<" | "<=" | ">" | ">=" | "in" | "not in") sum)*
    sum        := product (("+" | "-") product)*
    product    := unary (("*" | "/" | "//" | "%") unary)*
    unary      := "-" unary | power
    power      := postfix ("**" unary)?
    postfix    := primary (call | index | slice | "." NAME)*
    primary    := NUMBER | STRING | true | false | nil | NAME | "(" expr ")"
                | list | map | fn-literal
"""

from . import nodes as N
from .errors import syntax_error
from .lexer import tokenize

ASSIGN_OPS = {"=", "+=", "-=", "*=", "/=", "//=", "%="}
COMPARISON = {"==", "!=", "<", "<=", ">", ">="}


class Parser:
    def __init__(self, tokens):
        self.toks = tokens
        self.i = 0
        self.loop_depth = 0
        self.fn_depth = 0

    # ------------------------------------------------------------ helpers

    @property
    def tok(self):
        return self.toks[self.i]

    def peek(self, k=1):
        return self.toks[min(self.i + k, len(self.toks) - 1)]

    def at(self, type, value=None):
        t = self.tok
        return t.type == type and (value is None or t.value == value)

    def at_op(self, value):
        return self.at("OP", value)

    def at_kw(self, value):
        return self.at("KEYWORD", value)

    def advance(self):
        t = self.tok
        if t.type != "EOF":
            self.i += 1
        return t

    def error(self, message, token=None):
        token = token or self.tok
        return syntax_error(message, token, incomplete=token.type == "EOF")

    def describe(self, t):
        if t.type == "EOF":
            return "end of input"
        if t.type == "NEWLINE":
            return "end of line"
        if t.type == "STRING":
            return "a string"
        if t.type == "NUMBER":
            return f"number {t.value}"
        return f"'{t.value}'"

    def expect_op(self, value, what=None):
        if not self.at_op(value):
            raise self.error(f"expected '{value}'{' ' + what if what else ''}, found {self.describe(self.tok)}")
        return self.advance()

    def expect_name(self, what):
        if not self.at("IDENT"):
            raise self.error(f"expected {what}, found {self.describe(self.tok)}")
        return self.advance()

    def skip_newlines(self):
        while self.tok.type == "NEWLINE":
            self.advance()

    def skip_separators(self):
        while self.tok.type == "NEWLINE" or self.at_op(";"):
            self.advance()

    def pos(self, token):
        return {"line": token.line, "col": token.col}

    # ---------------------------------------------------------- statements

    def parse_program(self):
        body = []
        self.skip_separators()
        while not self.at("EOF"):
            body.append(self.statement())
            self.skip_separators()
        return body

    def block(self):
        self.expect_op("{", "to start a block")
        body = []
        self.skip_separators()
        while not self.at_op("}"):
            if self.at("EOF"):
                raise self.error("expected '}' to close the block")
            body.append(self.statement())
            self.skip_separators()
        self.advance()
        return body

    def end_statement(self):
        t = self.tok
        if t.type in ("NEWLINE", "EOF") or self.at_op(";") or self.at_op("}"):
            return
        raise self.error(f"expected end of statement, found {self.describe(t)}")

    def statement(self):
        t = self.tok
        if t.type == "KEYWORD":
            handler = {
                "let": self.let_stmt, "if": self.if_stmt, "while": self.while_stmt,
                "for": self.for_stmt, "try": self.try_stmt, "return": self.return_stmt,
                "break": self.break_stmt, "continue": self.continue_stmt,
                "throw": self.throw_stmt, "import": self.import_stmt,
            }.get(t.value)
            if t.value == "fn" and self.peek().type == "IDENT":
                return self.fn_def()
            if handler:
                return handler()
        return self.expr_stmt()

    def let_stmt(self):
        t = self.advance()
        name = self.expect_name("a variable name after 'let'")
        value = None
        if self.at_op("="):
            self.advance()
            self.skip_newlines()
            value = self.expression()
        self.end_statement()
        return N.Let(name.value, value, **self.pos(t))

    def fn_def(self):
        t = self.advance()
        name = self.advance().value
        fn = self.fn_rest(t, name)
        return N.Let(name, fn, **self.pos(t))

    def fn_rest(self, t, name):
        self.expect_op("(", "after fn")
        params, seen, has_default = [], set(), False
        while not self.at_op(")"):
            p = self.expect_name("a parameter name")
            if p.value in seen:
                raise self.error(f"duplicate parameter '{p.value}'", p)
            seen.add(p.value)
            default = None
            if self.at_op("="):
                self.advance()
                default = self.expression()
                has_default = True
            elif has_default:
                raise self.error(f"parameter '{p.value}' needs a default value because an earlier one has one", p)
            params.append(N.Param(p.value, default, **self.pos(p)))
            if not self.at_op(")"):
                self.expect_op(",", "between parameters")
        self.advance()
        saved = self.loop_depth
        self.loop_depth = 0
        self.fn_depth += 1
        try:
            if self.at_op("=>"):
                arrow = self.advance()
                self.skip_newlines()
                expr = self.expression()
                body = [N.Return(expr, **self.pos(arrow))]
            else:
                body = self.block()
        finally:
            self.loop_depth = saved
            self.fn_depth -= 1
        return N.FnLit(name, params, body, **self.pos(t))

    def lookahead_kw(self, *words):
        """True if, after optional newlines, the next keyword is one of words."""
        j = self.i
        while self.toks[j].type == "NEWLINE":
            j += 1
        t = self.toks[j]
        if t.type == "KEYWORD" and t.value in words:
            self.i = j
            return True
        return False

    def if_stmt(self):
        t = self.advance()
        branches = [(self.expression(), self.block())]
        else_body = None
        while self.lookahead_kw("elif", "else"):
            if self.advance().value == "elif":
                branches.append((self.expression(), self.block()))
            else:
                if self.at_kw("if"):  # allow "else if"
                    self.advance()
                    branches.append((self.expression(), self.block()))
                    continue
                else_body = self.block()
                break
        return N.If(branches, else_body, **self.pos(t))

    def loop_body(self):
        self.loop_depth += 1
        try:
            return self.block()
        finally:
            self.loop_depth -= 1

    def while_stmt(self):
        t = self.advance()
        cond = self.expression()
        return N.While(cond, self.loop_body(), **self.pos(t))

    def for_stmt(self):
        t = self.advance()
        first = self.expect_name("a loop variable after 'for'").value
        second = None
        if self.at_op(","):
            self.advance()
            second = self.expect_name("a second loop variable").value
        if not self.at_kw("in"):
            raise self.error(f"expected 'in' in for loop, found {self.describe(self.tok)}")
        self.advance()
        iterable = self.expression()
        return N.For(first, second, iterable, self.loop_body(), **self.pos(t))

    def try_stmt(self):
        t = self.advance()
        body = self.block()
        if not self.lookahead_kw("catch"):
            raise self.error("expected 'catch' after try block")
        self.advance()
        name = self.advance().value if self.at("IDENT") else None
        handler = self.block()
        return N.Try(body, name, handler, **self.pos(t))

    def return_stmt(self):
        t = self.advance()
        if self.fn_depth == 0:
            raise self.error("'return' outside of a function", t)
        value = None
        if not (self.tok.type in ("NEWLINE", "EOF") or self.at_op(";") or self.at_op("}")):
            value = self.expression()
        self.end_statement()
        return N.Return(value, **self.pos(t))

    def break_stmt(self):
        t = self.advance()
        if self.loop_depth == 0:
            raise self.error("'break' outside of a loop", t)
        self.end_statement()
        return N.Break(**self.pos(t))

    def continue_stmt(self):
        t = self.advance()
        if self.loop_depth == 0:
            raise self.error("'continue' outside of a loop", t)
        self.end_statement()
        return N.Continue(**self.pos(t))

    def throw_stmt(self):
        t = self.advance()
        value = self.expression()
        self.end_statement()
        return N.Throw(value, **self.pos(t))

    def import_stmt(self):
        t = self.advance()
        s = self.tok
        if s.type != "STRING" or len(s.value) != 1 or not isinstance(s.value[0], str):
            raise self.error("expected a plain string path after 'import'")
        self.advance()
        self.end_statement()
        return N.Import(s.value[0], **self.pos(t))

    def expr_stmt(self):
        t = self.tok
        expr = self.expression()
        if self.tok.type == "OP" and self.tok.value in ASSIGN_OPS:
            op = self.advance()
            if not isinstance(expr, (N.Name, N.Index, N.Attr)):
                raise self.error("can only assign to a variable, an index or a .field", t)
            self.skip_newlines()
            value = self.expression()
            self.end_statement()
            return N.Assign(expr, op.value, value, **self.pos(op))
        self.end_statement()
        return N.ExprStmt(expr, **self.pos(t))

    # --------------------------------------------------------- expressions

    def expression(self):
        return self.or_expr()

    def or_expr(self):
        left = self.and_expr()
        while self.at_kw("or"):
            t = self.advance()
            self.skip_newlines()
            left = N.Logical("or", left, self.and_expr(), **self.pos(t))
        return left

    def and_expr(self):
        left = self.not_expr()
        while self.at_kw("and"):
            t = self.advance()
            self.skip_newlines()
            left = N.Logical("and", left, self.not_expr(), **self.pos(t))
        return left

    def not_expr(self):
        if self.at_kw("not"):
            t = self.advance()
            return N.Unary("not", self.not_expr(), **self.pos(t))
        return self.comparison()

    def comparison(self):
        left = self.sum()
        while True:
            t = self.tok
            if t.type == "OP" and t.value in COMPARISON:
                op = t.value
            elif self.at_kw("in"):
                op = "in"
            elif self.at_kw("not") and self.peek().type == "KEYWORD" and self.peek().value == "in":
                self.advance()
                op = "not in"
            else:
                return left
            self.advance()
            self.skip_newlines()
            left = N.Binary(op, left, self.sum(), **self.pos(t))

    def sum(self):
        left = self.product()
        while self.at_op("+") or self.at_op("-"):
            t = self.advance()
            self.skip_newlines()
            left = N.Binary(t.value, left, self.product(), **self.pos(t))
        return left

    def product(self):
        left = self.unary()
        while self.tok.type == "OP" and self.tok.value in ("*", "/", "//", "%"):
            t = self.advance()
            self.skip_newlines()
            left = N.Binary(t.value, left, self.unary(), **self.pos(t))
        return left

    def unary(self):
        if self.at_op("-"):
            t = self.advance()
            return N.Unary("-", self.unary(), **self.pos(t))
        return self.power()

    def power(self):
        base = self.postfix()
        if self.at_op("**"):
            t = self.advance()
            self.skip_newlines()
            return N.Binary("**", base, self.unary(), **self.pos(t))
        return base

    def postfix(self):
        expr = self.primary()
        while True:
            if self.at_op("("):
                t = self.advance()
                args = []
                while not self.at_op(")"):
                    args.append(self.expression())
                    if not self.at_op(")"):
                        self.expect_op(",", "between arguments")
                self.advance()
                expr = N.Call(expr, args, **self.pos(t))
            elif self.at_op("["):
                t = self.advance()
                start = None if self.at_op(":") else self.expression()
                if self.at_op(":"):
                    self.advance()
                    end = None if self.at_op("]") else self.expression()
                    self.expect_op("]")
                    expr = N.Slice(expr, start, end, **self.pos(t))
                else:
                    self.expect_op("]")
                    expr = N.Index(expr, start, **self.pos(t))
            elif self.at_op("."):
                t = self.advance()
                name = self.expect_name("a field name after '.'")
                expr = N.Attr(expr, name.value, **self.pos(t))
            else:
                return expr

    def primary(self):
        t = self.tok
        if t.type == "NUMBER":
            self.advance()
            return N.Literal(t.value, **self.pos(t))
        if t.type == "STRING":
            self.advance()
            return self.string(t)
        if t.type == "IDENT":
            self.advance()
            return N.Name(t.value, **self.pos(t))
        if t.type == "KEYWORD":
            if t.value in ("true", "false", "nil"):
                self.advance()
                return N.Literal({"true": True, "false": False, "nil": None}[t.value], **self.pos(t))
            if t.value == "fn":
                self.advance()
                return self.fn_rest(t, "<anonymous>")
        if self.at_op("("):
            self.advance()
            expr = self.expression()
            self.expect_op(")")
            return expr
        if self.at_op("["):
            self.advance()
            items = []
            while not self.at_op("]"):
                items.append(self.expression())
                if not self.at_op("]"):
                    self.expect_op(",", "between list items")
            self.advance()
            return N.ListLit(items, **self.pos(t))
        if self.at_op("{"):
            return self.map_literal()
        raise self.error(f"unexpected {self.describe(t)}")

    def map_literal(self):
        t = self.advance()
        pairs = []
        self.skip_newlines()
        while not self.at_op("}"):
            k = self.tok
            if k.type == "IDENT" and self.peek().type == "OP" and self.peek().value == ":":
                self.advance()
                key = N.Literal(k.value, **self.pos(k))  # {name: 1} means {"name": 1}
            else:
                key = self.expression()
            self.expect_op(":", "between key and value")
            self.skip_newlines()
            pairs.append((key, self.expression()))
            self.skip_newlines()
            if not self.at_op("}"):
                self.expect_op(",", "between map entries")
                self.skip_newlines()
        self.advance()
        return N.MapLit(pairs, **self.pos(t))

    def string(self, t):
        parts = []
        for part in t.value:
            if isinstance(part, str):
                parts.append(part)
            else:
                src, line, col = part
                sub = Parser(tokenize(src, line, col))
                sub.skip_newlines()
                expr = sub.expression()
                sub.skip_newlines()
                if not sub.at("EOF"):
                    raise sub.error(f"unexpected {sub.describe(sub.tok)} in string interpolation")
                parts.append(expr)
        if len(parts) == 1 and isinstance(parts[0], str):
            return N.Literal(parts[0], **self.pos(t))
        return N.Interpolated(parts, **self.pos(t))


def parse(source):
    return Parser(tokenize(source)).parse_program()
