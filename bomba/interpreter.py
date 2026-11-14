"""Tree-walking interpreter."""

import os

from . import nodes as N
from .errors import BombaError, BombaThrow
from .lexer import tokenize
from .parser import Parser
from .values import (
    Builtin, Function, display, equal, hashable_key, is_number, truthy, type_name,
)


class ReturnSignal(Exception):
    def __init__(self, value):
        self.value = value


class BreakSignal(Exception):
    pass


class ContinueSignal(Exception):
    pass


class Env:
    __slots__ = ("vars", "parent")

    def __init__(self, parent=None):
        self.vars = {}
        self.parent = parent

    def define(self, name, value):
        self.vars[name] = value

    def lookup(self, name):
        env = self
        while env is not None:
            if name in env.vars:
                return env.vars[name]
            env = env.parent
        raise BombaError("NameError", f"'{name}' is not defined")

    def assign(self, name, value):
        env = self
        while env is not None:
            if name in env.vars:
                env.vars[name] = value
                return
            env = env.parent
        raise BombaError("NameError", f"'{name}' is not defined (declare it first with 'let {name} = ...')")


def err(kind, message):
    return BombaError(kind, message)


class Interpreter:
    def __init__(self, out=None, read=None, max_depth=800):
        from .builtins import install
        self.out = out or (lambda text: print(text, flush=True))
        self.read = read or input
        self.max_depth = max_depth
        self.depth = 0
        self.builtins = Env()
        install(self)
        self.globals = Env(self.builtins)
        self.env = self.globals
        self.origin = ("<main>", "")
        self.dirs = [os.getcwd()]
        self.imported = set()

        self._eval = {
            N.Literal: self.eval_literal, N.Interpolated: self.eval_interpolated,
            N.Name: self.eval_name, N.ListLit: self.eval_list, N.MapLit: self.eval_map,
            N.FnLit: self.eval_fn, N.Unary: self.eval_unary, N.Binary: self.eval_binary,
            N.Logical: self.eval_logical, N.Call: self.eval_call, N.Index: self.eval_index,
            N.Slice: self.eval_slice, N.Attr: self.eval_attr,
        }
        self._exec = {
            N.Let: self.exec_let, N.Assign: self.exec_assign, N.ExprStmt: self.exec_expr,
            N.If: self.exec_if, N.While: self.exec_while, N.For: self.exec_for,
            N.Break: self.exec_break, N.Continue: self.exec_continue, N.Return: self.exec_return,
            N.Try: self.exec_try, N.Throw: self.exec_throw, N.Import: self.exec_import,
        }

    # ------------------------------------------------------------- running

    def parse(self, source, filename="<main>"):
        try:
            return Parser(tokenize(source)).parse_program()
        except BombaError as e:
            raise e.attach(filename=filename, source=source)

    def run(self, source, filename="<main>"):
        """Run source code in the global scope.

        Returns the value of the last expression statement (used by the REPL).
        """
        program = self.parse(source, filename)
        saved_origin = self.origin
        self.origin = (filename, source)
        if filename not in ("<main>", "<repl>", "<string>") and os.path.exists(filename):
            self.dirs.append(os.path.dirname(os.path.abspath(filename)))
            pushed = True
        else:
            pushed = False
        result = None
        try:
            for stmt in program:
                if isinstance(stmt, N.ExprStmt):
                    result = self.evaluate(stmt.expr)
                else:
                    self.execute(stmt)
                    result = None
        finally:
            self.origin = saved_origin
            if pushed:
                self.dirs.pop()
        return result

    def run_file(self, path):
        with open(path, encoding="utf-8") as f:
            source = f.read()
        self.imported.add(os.path.abspath(path))
        return self.run(source, path)

    # ---------------------------------------------------------- dispatching

    def evaluate(self, node):
        try:
            return self._eval[type(node)](node)
        except BombaError as e:
            if e.line is None:
                e.attach(node.line, node.col, *self.origin)
            raise

    def execute(self, node):
        try:
            self._exec[type(node)](node)
        except BombaError as e:
            if e.line is None:
                e.attach(node.line, node.col, *self.origin)
            raise

    def execute_block(self, body, env):
        saved = self.env
        self.env = env
        try:
            for stmt in body:
                self.execute(stmt)
        finally:
            self.env = saved

    # ---------------------------------------------------------- expressions

    def eval_literal(self, node):
        return node.value

    def eval_interpolated(self, node):
        return "".join(p if isinstance(p, str) else display(self.evaluate(p)) for p in node.parts)

    def eval_name(self, node):
        return self.env.lookup(node.name)

    def eval_list(self, node):
        return [self.evaluate(x) for x in node.items]

    def eval_map(self, node):
        result = {}
        for k, v in node.pairs:
            result[hashable_key(self.evaluate(k))] = self.evaluate(v)
        return result

    def eval_fn(self, node):
        return Function(node.name, node.params, node.body, self.env, self.origin)

    def eval_unary(self, node):
        v = self.evaluate(node.operand)
        if node.op == "not":
            return not truthy(v)
        if not is_number(v):
            raise err("TypeError", f"cannot negate a {type_name(v)}")
        return -v

    def eval_logical(self, node):
        left = self.evaluate(node.left)
        if node.op == "or":
            return left if truthy(left) else self.evaluate(node.right)
        return self.evaluate(node.right) if truthy(left) else left

    def eval_binary(self, node):
        a = self.evaluate(node.left)
        b = self.evaluate(node.right)
        return self.binop(node.op, a, b)

    def binop(self, op, a, b):
        if op == "==":
            return equal(a, b)
        if op == "!=":
            return not equal(a, b)
        if op in ("in", "not in"):
            if isinstance(b, str):
                if not isinstance(a, str):
                    raise err("TypeError", f"'in <string>' needs a string on the left, not a {type_name(a)}")
                found = a in b
            elif isinstance(b, list):
                found = any(equal(a, x) for x in b)
            elif isinstance(b, dict):
                found = hashable_key(a) in b
            else:
                raise err("TypeError", f"cannot use 'in' on a {type_name(b)}")
            return found if op == "in" else not found

        num = is_number(a) and is_number(b)
        if op == "+":
            if num:
                return a + b
            if isinstance(a, str) and isinstance(b, str):
                return a + b
            if isinstance(a, list) and isinstance(b, list):
                return a + b
            if isinstance(a, dict) and isinstance(b, dict):
                return {**a, **b}
            hint = " (tip: use str() or \"{...}\" interpolation)" if isinstance(a, str) or isinstance(b, str) else ""
            raise err("TypeError", f"cannot add {type_name(a)} and {type_name(b)}{hint}")
        if op == "*":
            if num:
                return a * b
            if isinstance(a, (str, list)) and isinstance(b, int) and not isinstance(b, bool):
                return a * b
            if isinstance(b, (str, list)) and isinstance(a, int) and not isinstance(a, bool):
                return a * b
            raise err("TypeError", f"cannot multiply {type_name(a)} and {type_name(b)}")
        if op in ("-", "/", "//", "%", "**"):
            if not num:
                raise err("TypeError", f"cannot use '{op}' on {type_name(a)} and {type_name(b)}")
            if op == "-":
                return a - b
            if op in ("/", "//", "%") and b == 0:
                raise err("ZeroDivisionError", "division by zero")
            if op == "/":
                return a / b
            if op == "//":
                return a // b
            if op == "%":
                return a % b
            try:
                return a ** b
            except OverflowError:
                raise err("OverflowError", "number too large")
        if op in ("<", "<=", ">", ">="):
            if not (num or (isinstance(a, str) and isinstance(b, str))):
                raise err("TypeError", f"cannot compare {type_name(a)} and {type_name(b)} with '{op}'")
            return {"<": a < b, "<=": a <= b, ">": a > b, ">=": a >= b}[op]
        raise err("RuntimeError", f"unknown operator {op}")

    def eval_call(self, node):
        callee = self.evaluate(node.callee)
        args = [self.evaluate(a) for a in node.args]
        return self.call(callee, args)

    def call(self, fn, args):
        if isinstance(fn, Builtin):
            return fn.fn(self, args)
        if not isinstance(fn, Function):
            raise err("TypeError", f"a {type_name(fn)} is not callable")
        params = fn.params
        required = sum(1 for p in params if p.default is None)
        if not required <= len(args) <= len(params):
            expected = str(len(params)) if required == len(params) else f"{required} to {len(params)}"
            raise err("TypeError", f"{fn.name}() takes {expected} argument{'s' if expected != '1' else ''}, got {len(args)}")
        if self.depth >= self.max_depth:
            raise err("RecursionError", f"maximum recursion depth ({self.max_depth}) exceeded")
        env = Env(fn.closure)
        saved_env, saved_origin = self.env, self.origin
        self.env, self.origin = env, fn.origin
        self.depth += 1
        try:
            for i, p in enumerate(params):
                env.define(p.name, args[i] if i < len(args) else self.evaluate(p.default))
            for stmt in fn.body:
                self.execute(stmt)
            return None
        except ReturnSignal as r:
            return r.value
        except RecursionError:
            raise err("RecursionError", "maximum recursion depth exceeded")
        finally:
            self.depth -= 1
            self.env, self.origin = saved_env, saved_origin

    def index_value(self, obj, idx):
        if isinstance(obj, (list, str)):
            if not isinstance(idx, int) or isinstance(idx, bool):
                if isinstance(idx, float) and idx.is_integer():
                    idx = int(idx)
                else:
                    raise err("TypeError", f"{type_name(obj)} index must be an int, not {type_name(idx)}")
            if not -len(obj) <= idx < len(obj):
                raise err("IndexError", f"index {idx} out of range for {type_name(obj)} of length {len(obj)}")
            return obj[idx]
        if isinstance(obj, dict):
            key = hashable_key(idx)
            if key not in obj:
                raise err("KeyError", f"key {display(idx, True)} not found (tip: use get(map, key, default))")
            return obj[key]
        raise err("TypeError", f"cannot index a {type_name(obj)}")

    def eval_index(self, node):
        return self.index_value(self.evaluate(node.obj), self.evaluate(node.index))

    def eval_slice(self, node):
        obj = self.evaluate(node.obj)
        if not isinstance(obj, (list, str)):
            raise err("TypeError", f"cannot slice a {type_name(obj)}")
        bounds = []
        for b in (node.start, node.end):
            v = None if b is None else self.evaluate(b)
            if v is not None and (not isinstance(v, int) or isinstance(v, bool)):
                raise err("TypeError", f"slice bounds must be ints, not {type_name(v)}")
            bounds.append(v)
        return obj[bounds[0]:bounds[1]]

    def eval_attr(self, node):
        obj = self.evaluate(node.obj)
        if not isinstance(obj, dict):
            raise err("TypeError", f"cannot read .{node.name} of a {type_name(obj)} (only maps have fields)")
        if node.name not in obj:
            raise err("KeyError", f"map has no field '{node.name}'")
        return obj[node.name]

    # ----------------------------------------------------------- statements

    def exec_let(self, node):
        self.env.define(node.name, None if node.value is None else self.evaluate(node.value))

    def exec_assign(self, node):
        target, op = node.target, node.op
        if isinstance(target, N.Name):
            value = self.evaluate(node.value)
            if op != "=":
                value = self.binop(op[:-1], self.env.lookup(target.name), value)
            self.env.assign(target.name, value)
            return
        obj = self.evaluate(target.obj)
        if isinstance(target, N.Attr):
            if not isinstance(obj, dict):
                raise err("TypeError", f"cannot set .{target.name} on a {type_name(obj)}")
            key = target.name
            value = self.evaluate(node.value)
            if op != "=":
                if key not in obj:
                    raise err("KeyError", f"map has no field '{key}'")
                value = self.binop(op[:-1], obj[key], value)
            obj[key] = value
            return
        idx = self.evaluate(target.index)
        value = self.evaluate(node.value)
        if op != "=":
            value = self.binop(op[:-1], self.index_value(obj, idx), value)
        if isinstance(obj, list):
            self.index_value(obj, idx)  # bounds/type check
            obj[int(idx)] = value
        elif isinstance(obj, dict):
            obj[hashable_key(idx)] = value
        else:
            raise err("TypeError", f"cannot assign into a {type_name(obj)}")

    def exec_expr(self, node):
        self.evaluate(node.expr)

    def exec_if(self, node):
        for cond, body in node.branches:
            if truthy(self.evaluate(cond)):
                self.execute_block(body, Env(self.env))
                return
        if node.else_body is not None:
            self.execute_block(node.else_body, Env(self.env))

    def exec_while(self, node):
        while truthy(self.evaluate(node.cond)):
            try:
                self.execute_block(node.body, Env(self.env))
            except BreakSignal:
                break
            except ContinueSignal:
                continue

    def exec_for(self, node):
        iterable = self.evaluate(node.iterable)
        if isinstance(iterable, dict):
            items = list(iterable.items()) if node.second else [(k, None) for k in iterable]
        elif isinstance(iterable, (list, str)):
            items = list(enumerate(iterable)) if node.second else [(x, None) for x in iterable]
        else:
            raise err("TypeError", f"cannot loop over a {type_name(iterable)}")
        for first, second in items:
            env = Env(self.env)
            env.define(node.first, first)
            if node.second:
                env.define(node.second, second)
            try:
                self.execute_block(node.body, env)
            except BreakSignal:
                break
            except ContinueSignal:
                continue

    def exec_break(self, node):
        raise BreakSignal()

    def exec_continue(self, node):
        raise ContinueSignal()

    def exec_return(self, node):
        raise ReturnSignal(None if node.value is None else self.evaluate(node.value))

    def exec_try(self, node):
        try:
            self.execute_block(node.body, Env(self.env))
        except BombaError as e:
            if e.kind == "SyntaxError" and e.incomplete:
                raise
            if isinstance(e, BombaThrow):
                caught = e.value
            else:
                caught = {"type": e.kind, "message": e.message, "line": e.line}
            env = Env(self.env)
            if node.name:
                env.define(node.name, caught)
            self.execute_block(node.handler, env)

    def exec_throw(self, node):
        value = self.evaluate(node.value)
        raise BombaThrow(value, display(value))

    def exec_import(self, node):
        path = node.path
        if not path.endswith(".bmba"):
            path += ".bmba"
        full = os.path.abspath(os.path.join(self.dirs[-1], path))
        if full in self.imported:
            return
        if not os.path.exists(full):
            raise err("ImportError", f"cannot find module '{node.path}' (looked for {full})")
        self.imported.add(full)
        with open(full, encoding="utf-8") as f:
            source = f.read()
        saved_env = self.env
        self.env = self.globals
        try:
            self.run(source, full)
        finally:
            self.env = saved_env
