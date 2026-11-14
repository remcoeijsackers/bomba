"""Runtime values and how they print.

bomba values map onto Python values:

    nil -> None      bool -> bool     int/float -> int/float
    string -> str    list -> list     map -> dict
    function -> Function / Builtin
"""

import math

from .errors import BombaError


class Function:
    __slots__ = ("name", "params", "body", "closure", "origin")

    def __init__(self, name, params, body, closure, origin):
        self.name = name
        self.params = params
        self.body = body
        self.closure = closure
        self.origin = origin  # (filename, source) for error reports

    def __repr__(self):
        return f"<fn {self.name}>"


class Builtin:
    __slots__ = ("name", "fn")

    def __init__(self, name, fn):
        self.name = name
        self.fn = fn

    def __repr__(self):
        return f"<builtin {self.name}>"


def type_name(v):
    if v is None:
        return "nil"
    if isinstance(v, bool):
        return "bool"
    if isinstance(v, int):
        return "int"
    if isinstance(v, float):
        return "float"
    if isinstance(v, str):
        return "string"
    if isinstance(v, list):
        return "list"
    if isinstance(v, dict):
        return "map"
    if isinstance(v, (Function, Builtin)):
        return "function"
    return type(v).__name__


def is_number(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def truthy(v):
    if v is None or v is False:
        return False
    if v is True:
        return True
    if is_number(v):
        return v != 0
    if isinstance(v, (str, list, dict)):
        return len(v) > 0
    return True


def equal(a, b):
    # true != 1 and false != 0, unlike Python
    if isinstance(a, bool) or isinstance(b, bool):
        return type(a) is type(b) and a == b
    if isinstance(a, list) and isinstance(b, list):
        return len(a) == len(b) and all(equal(x, y) for x, y in zip(a, b))
    if isinstance(a, dict) and isinstance(b, dict):
        return a.keys() == b.keys() and all(equal(a[k], b[k]) for k in a)
    if is_number(a) and is_number(b):
        return a == b
    if type(a) is not type(b):
        return False
    return a == b


def format_number(n):
    if isinstance(n, float):
        if math.isinf(n):
            return "inf" if n > 0 else "-inf"
        if math.isnan(n):
            return "nan"
        return repr(n)
    return str(n)


def quote(s):
    out = s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n").replace("\t", "\\t")
    return f'"{out}"'


def display(v, nested=False, _seen=None):
    """How print() and string interpolation show a value."""
    if v is None:
        return "nil"
    if v is True:
        return "true"
    if v is False:
        return "false"
    if is_number(v):
        return format_number(v)
    if isinstance(v, str):
        return quote(v) if nested else v
    if isinstance(v, (list, dict)):
        _seen = _seen or set()
        if id(v) in _seen:
            return "[...]" if isinstance(v, list) else "{...}"
        _seen = _seen | {id(v)}
        if isinstance(v, list):
            return "[" + ", ".join(display(x, True, _seen) for x in v) + "]"
        return "{" + ", ".join(f"{display(k, True, _seen)}: {display(x, True, _seen)}" for k, x in v.items()) + "}"
    if isinstance(v, Function):
        return f"<fn {v.name}>"
    if isinstance(v, Builtin):
        return f"<builtin {v.name}>"
    return str(v)


def hashable_key(k):
    if isinstance(k, (list, dict)) or isinstance(k, (Function, Builtin)):
        raise BombaError("TypeError", f"a {type_name(k)} cannot be used as a map key")
    if isinstance(k, float) and k.is_integer():
        return int(k)
    return k
