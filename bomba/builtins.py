"""Built-in functions and the ``math`` module."""

import math
import time

from .errors import BombaError
from .values import Builtin, Function, display, equal, hashable_key, is_number, truthy, type_name


def err(kind, message):
    return BombaError(kind, message)


REGISTRY = {}


def builtin(name=None, arity=None):
    """Register a builtin. ``arity`` is an int or (min, max) tuple; max None = any."""
    def wrap(fn):
        n = name or fn.__name__.rstrip("_")

        def checked(interp, args):
            if arity is not None:
                lo, hi = (arity, arity) if isinstance(arity, int) else arity
                if len(args) < lo or (hi is not None and len(args) > hi):
                    if lo == hi:
                        want = f"{lo} argument{'s' if lo != 1 else ''}"
                    elif hi is None:
                        want = f"at least {lo} argument{'s' if lo != 1 else ''}"
                    else:
                        want = f"{lo} to {hi} arguments"
                    raise err("TypeError", f"{n}() takes {want}, got {len(args)}")
            return fn(interp, *args)

        REGISTRY[n] = checked
        return fn
    return wrap


def need(value, kinds, fname, what="argument"):
    names = {"list": list, "map": dict, "string": str, "function": (Function, Builtin)}
    for k in kinds:
        if k == "number" and is_number(value):
            return value
        if k == "int" and isinstance(value, int) and not isinstance(value, bool):
            return value
        if k in names and isinstance(value, names[k]):
            return value
    raise err("TypeError", f"{fname}() expects {' or '.join(kinds)} as {what}, got {type_name(value)}")


# ------------------------------------------------------------------ core / io

@builtin(arity=(0, None))
def print_(interp, *args):
    interp.out(" ".join(display(a) for a in args))


@builtin(arity=(0, 1))
def input_(interp, prompt=""):
    try:
        return interp.read(display(prompt))
    except EOFError:
        return None


@builtin(arity=1)
def type_(interp, v):
    return type_name(v)


@builtin(arity=1)
def len_(interp, v):
    need(v, ["string", "list", "map"], "len")
    return len(v)


@builtin(arity=1)
def str_(interp, v):
    return display(v)


@builtin(arity=1)
def repr_(interp, v):
    return display(v, nested=True)


@builtin(arity=1)
def int_(interp, v):
    if isinstance(v, bool):
        return int(v)
    if is_number(v):
        return int(v)
    if isinstance(v, str):
        try:
            return int(v.strip())
        except ValueError:
            try:
                return int(float(v.strip()))
            except ValueError:
                raise err("ValueError", f"cannot convert {display(v, True)} to int")
    raise err("TypeError", f"cannot convert {type_name(v)} to int")


@builtin(arity=1)
def float_(interp, v):
    if is_number(v):
        return float(v)
    if isinstance(v, str):
        try:
            return float(v.strip())
        except ValueError:
            raise err("ValueError", f"cannot convert {display(v, True)} to float")
    raise err("TypeError", f"cannot convert {type_name(v)} to float")


@builtin(arity=1)
def bool_(interp, v):
    return truthy(v)


@builtin(arity=(1, 2))
def assert_(interp, cond, message="assertion failed"):
    if not truthy(cond):
        raise err("AssertionError", display(message))


@builtin(arity=0)
def clock(interp):
    return time.perf_counter()


# --------------------------------------------------------------------- lists

@builtin(arity=(1, 3))
def range_(interp, a, b=None, step=1):
    for v in (a, b, step):
        if v is not None:
            need(v, ["int"], "range")
    if step == 0:
        raise err("ValueError", "range() step cannot be 0")
    start, stop = (0, a) if b is None else (a, b)
    if abs((stop - start) // step) > 10_000_000:
        raise err("ValueError", "range() is too large")
    return list(range(start, stop, step))


@builtin(arity=2)
def push(interp, lst, value):
    need(lst, ["list"], "push")
    lst.append(value)
    return lst


@builtin(arity=(1, 2))
def pop(interp, lst, index=-1):
    need(lst, ["list"], "pop")
    if not lst:
        raise err("IndexError", "pop() from an empty list")
    need(index, ["int"], "pop", "index")
    if not -len(lst) <= index < len(lst):
        raise err("IndexError", f"pop() index {index} out of range")
    return lst.pop(index)


@builtin(arity=3)
def insert(interp, lst, index, value):
    need(lst, ["list"], "insert")
    need(index, ["int"], "insert", "index")
    lst.insert(index, value)
    return lst


@builtin(arity=2)
def remove(interp, coll, key):
    need(coll, ["list", "map"], "remove")
    if isinstance(coll, list):
        for i, x in enumerate(coll):
            if equal(x, key):
                del coll[i]
                return True
        return False
    k = hashable_key(key)
    if k in coll:
        del coll[k]
        return True
    return False


@builtin(arity=2)
def index_of(interp, coll, value):
    need(coll, ["list", "string"], "index_of")
    if isinstance(coll, str):
        need(value, ["string"], "index_of", "value")
        return coll.find(value)
    for i, x in enumerate(coll):
        if equal(x, value):
            return i
    return -1


@builtin(arity=1)
def reverse(interp, coll):
    need(coll, ["list", "string"], "reverse")
    return coll[::-1]


def _sort_key(v):
    if is_number(v):
        return (0, v)
    if isinstance(v, str):
        return (1, v)
    raise err("TypeError", f"cannot sort a list containing a {type_name(v)} (pass a key function)")


@builtin(arity=(1, 2))
def sort(interp, lst, key=None):
    need(lst, ["list"], "sort")
    if key is None:
        keys = [_sort_key(x) for x in lst]
    else:
        need(key, ["function"], "sort", "key")
        keys = [_sort_key(interp.call(key, [x])) for x in lst]
    kinds = {k[0] for k in keys}
    if len(kinds) > 1:
        raise err("TypeError", "cannot sort a mix of numbers and strings")
    order = sorted(range(len(lst)), key=lambda i: keys[i][1])
    return [lst[i] for i in order]


@builtin(arity=2)
def map_(interp, lst, fn):
    need(lst, ["list"], "map")
    need(fn, ["function"], "map", "second argument")
    return [interp.call(fn, [x]) for x in lst]


@builtin(arity=2)
def filter_(interp, lst, fn):
    need(lst, ["list"], "filter")
    need(fn, ["function"], "filter", "second argument")
    return [x for x in lst if truthy(interp.call(fn, [x]))]


@builtin(arity=(2, 3))
def reduce(interp, lst, fn, *initial):
    need(lst, ["list"], "reduce")
    need(fn, ["function"], "reduce", "second argument")
    items = list(lst)
    if initial:
        acc = initial[0]
    elif items:
        acc = items.pop(0)
    else:
        raise err("ValueError", "reduce() of an empty list needs an initial value")
    for x in items:
        acc = interp.call(fn, [acc, x])
    return acc


@builtin(arity=2)
def any_(interp, lst, fn):
    need(lst, ["list"], "any")
    return any(truthy(interp.call(fn, [x])) for x in lst)


@builtin(arity=2)
def all_(interp, lst, fn):
    need(lst, ["list"], "all")
    return all(truthy(interp.call(fn, [x])) for x in lst)


@builtin(arity=2)
def zip_(interp, a, b):
    need(a, ["list"], "zip")
    need(b, ["list"], "zip")
    return [[x, y] for x, y in zip(a, b)]


def _numbers(args, fname):
    items = args[0] if len(args) == 1 and isinstance(args[0], list) else list(args)
    if not items:
        raise err("ValueError", f"{fname}() of an empty list")
    for x in items:
        need(x, ["number"], fname, "item")
    return items


@builtin(arity=(1, None))
def min_(interp, *args):
    return min(_numbers(args, "min"))


@builtin(arity=(1, None))
def max_(interp, *args):
    return max(_numbers(args, "max"))


@builtin(arity=1)
def sum_(interp, lst):
    need(lst, ["list"], "sum")
    return sum(_numbers([lst], "sum")) if lst else 0


# ---------------------------------------------------------------------- maps

@builtin(arity=1)
def keys(interp, m):
    need(m, ["map"], "keys")
    return list(m.keys())


@builtin(arity=1)
def values(interp, m):
    need(m, ["map"], "values")
    return list(m.values())


@builtin(arity=1)
def items(interp, m):
    need(m, ["map"], "items")
    return [[k, v] for k, v in m.items()]


@builtin(arity=(2, 3))
def get(interp, coll, key, default=None):
    need(coll, ["map", "list"], "get")
    if isinstance(coll, list):
        if isinstance(key, int) and -len(coll) <= key < len(coll):
            return coll[key]
        return default
    return coll.get(hashable_key(key), default)


@builtin(arity=1)
def copy(interp, v):
    if isinstance(v, list):
        return list(v)
    if isinstance(v, dict):
        return dict(v)
    return v


# ------------------------------------------------------------------- strings

@builtin(arity=(1, 2))
def split(interp, s, sep=None):
    need(s, ["string"], "split")
    if sep is None:
        return s.split()
    need(sep, ["string"], "split", "separator")
    if sep == "":
        return list(s)
    return s.split(sep)


@builtin(arity=(1, 2))
def join(interp, lst, sep=""):
    need(lst, ["list"], "join")
    need(sep, ["string"], "join", "separator")
    return sep.join(display(x) for x in lst)


@builtin(arity=1)
def upper(interp, s):
    return need(s, ["string"], "upper").upper()


@builtin(arity=1)
def lower(interp, s):
    return need(s, ["string"], "lower").lower()


@builtin(arity=1)
def trim(interp, s):
    return need(s, ["string"], "trim").strip()


@builtin(arity=3)
def replace(interp, s, old, new):
    need(s, ["string"], "replace")
    need(old, ["string"], "replace")
    need(new, ["string"], "replace")
    return s.replace(old, new)


@builtin(arity=2)
def starts_with(interp, s, prefix):
    return need(s, ["string"], "starts_with").startswith(need(prefix, ["string"], "starts_with"))


@builtin(arity=2)
def ends_with(interp, s, suffix):
    return need(s, ["string"], "ends_with").endswith(need(suffix, ["string"], "ends_with"))


@builtin(arity=(2, 3))
def pad(interp, value, width, fill=" "):
    """Pad on the left (positive width) or right (negative width)."""
    s = display(value)
    need(width, ["int"], "pad", "width")
    need(fill, ["string"], "pad", "fill")
    if len(fill) != 1:
        raise err("ValueError", "pad() fill must be a single character")
    return s.rjust(width, fill) if width >= 0 else s.ljust(-width, fill)


@builtin(arity=1)
def chr_(interp, n):
    need(n, ["int"], "chr")
    try:
        return chr(n)
    except (ValueError, OverflowError):
        raise err("ValueError", f"chr() code {n} out of range")


@builtin(arity=1)
def ord_(interp, s):
    need(s, ["string"], "ord")
    if len(s) != 1:
        raise err("ValueError", "ord() expects a single character")
    return ord(s)


# --------------------------------------------------------------------- maths

@builtin(arity=1)
def abs_(interp, x):
    return abs(need(x, ["number"], "abs"))


@builtin(arity=(1, 2))
def round_(interp, x, digits=0):
    need(x, ["number"], "round")
    need(digits, ["int"], "round", "digits")
    r = round(x, digits)
    return int(r) if digits == 0 else r


def _math_fn(name, fn, arity=1):
    def call(interp, args):
        if len(args) != arity:
            raise err("TypeError", f"math.{name}() takes {arity} argument{'s' if arity != 1 else ''}, got {len(args)}")
        for a in args:
            need(a, ["number"], f"math.{name}")
        try:
            return fn(*args)
        except (ValueError, OverflowError) as e:
            raise err("ValueError", f"math.{name}(): {e}")
    return Builtin(f"math.{name}", call)


def math_module(rng):
    m = {
        "pi": math.pi,
        "e": math.e,
        "inf": math.inf,
    }
    for name, fn, arity in [
        ("sqrt", math.sqrt, 1), ("floor", math.floor, 1), ("ceil", math.ceil, 1),
        ("sin", math.sin, 1), ("cos", math.cos, 1), ("tan", math.tan, 1),
        ("atan2", math.atan2, 2), ("log", math.log, 1), ("log10", math.log10, 1),
        ("exp", math.exp, 1), ("pow", math.pow, 2), ("hypot", math.hypot, 2),
    ]:
        m[name] = _math_fn(name, fn, arity)

    def rand(interp, args):
        if args:
            raise err("TypeError", "math.random() takes no arguments")
        return rng.random()

    def randint(interp, args):
        if len(args) != 2:
            raise err("TypeError", f"math.randint() takes 2 arguments, got {len(args)}")
        a, b = (need(x, ["int"], "math.randint") for x in args)
        if a > b:
            raise err("ValueError", "math.randint(a, b) needs a <= b")
        return rng.randint(a, b)

    def seed(interp, args):
        rng.seed(args[0] if args else None)

    m["random"] = Builtin("math.random", rand)
    m["randint"] = Builtin("math.randint", randint)
    m["seed"] = Builtin("math.seed", seed)
    return m


def install(interp):
    for name, fn in REGISTRY.items():
        interp.builtins.define(name, Builtin(name, fn))
    interp.builtins.define("math", math_module(interp.rng))
