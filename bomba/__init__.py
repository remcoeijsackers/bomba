"""bomba — a small, friendly scripting language."""

from .errors import BombaError
from .interpreter import Interpreter
from .parser import parse
from .values import display

__version__ = "1.0.0"
__all__ = ["BombaError", "Interpreter", "parse", "display", "run", "__version__"]


def run(source, out=None, read=None, filename="<string>"):
    """Run a piece of bomba code and return the value of its last expression."""
    return Interpreter(out=out, read=read).run(source, filename)
