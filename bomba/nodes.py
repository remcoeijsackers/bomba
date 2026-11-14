"""Syntax tree nodes. Every node remembers where it came from (line, col)."""

from dataclasses import dataclass, field


@dataclass
class Node:
    line: int = field(default=0, kw_only=True, repr=False)
    col: int = field(default=0, kw_only=True, repr=False)


# ---------------------------------------------------------------- expressions

@dataclass
class Literal(Node):
    value: object


@dataclass
class Interpolated(Node):
    parts: list  # str | Node


@dataclass
class Name(Node):
    name: str


@dataclass
class ListLit(Node):
    items: list


@dataclass
class MapLit(Node):
    pairs: list  # [(key_node, value_node)]


@dataclass
class Param(Node):
    name: str
    default: object = None  # Node | None


@dataclass
class FnLit(Node):
    name: str
    params: list  # [Param]
    body: list


@dataclass
class Unary(Node):
    op: str
    operand: Node


@dataclass
class Binary(Node):
    op: str
    left: Node
    right: Node


@dataclass
class Logical(Node):
    op: str  # "and" | "or"
    left: Node
    right: Node


@dataclass
class Call(Node):
    callee: Node
    args: list


@dataclass
class Index(Node):
    obj: Node
    index: Node


@dataclass
class Slice(Node):
    obj: Node
    start: object  # Node | None
    end: object    # Node | None


@dataclass
class Attr(Node):
    obj: Node
    name: str


# ----------------------------------------------------------------- statements

@dataclass
class Let(Node):
    name: str
    value: object  # Node | None


@dataclass
class Assign(Node):
    target: Node  # Name | Index | Attr
    op: str       # "=", "+=", ...
    value: Node


@dataclass
class ExprStmt(Node):
    expr: Node


@dataclass
class If(Node):
    branches: list  # [(cond, body)]
    else_body: object  # list | None


@dataclass
class While(Node):
    cond: Node
    body: list


@dataclass
class For(Node):
    first: str
    second: object  # str | None
    iterable: Node
    body: list


@dataclass
class Break(Node):
    pass


@dataclass
class Continue(Node):
    pass


@dataclass
class Return(Node):
    value: object  # Node | None


@dataclass
class Try(Node):
    body: list
    name: object  # str | None
    handler: list


@dataclass
class Throw(Node):
    value: Node


@dataclass
class Import(Node):
    path: str
