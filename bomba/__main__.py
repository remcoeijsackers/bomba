"""Command line: ``bomba [file.bmba]`` or ``python -m bomba``."""

import argparse
import pprint
import sys

from . import __version__
from .errors import BombaError
from .interpreter import Interpreter
from .lexer import tokenize
from .parser import parse
from .values import display

BANNER = f"bomba {__version__} — type :help for help, :quit to leave"

HELP = """\
Enter statements or expressions; results are shown automatically.
Blocks can span multiple lines: the prompt changes to ... until the block is closed.

  :help        this text
  :vars        list the variables you defined
  :reset       start over with a clean interpreter
  :quit        leave (Ctrl-D works too)
"""


def repl():
    interp = Interpreter()
    print(BANNER)
    buffer = []
    while True:
        try:
            line = input("... " if buffer else "bomba> ")
        except EOFError:
            print()
            return 0
        except KeyboardInterrupt:
            print("\n(interrupted)")
            buffer = []
            continue

        if not buffer and line.strip().startswith(":"):
            cmd = line.strip()
            if cmd in (":q", ":quit", ":exit"):
                return 0
            if cmd == ":help":
                print(HELP)
            elif cmd == ":vars":
                for name, value in interp.globals.vars.items():
                    print(f"  {name} = {display(value, nested=True)}")
            elif cmd == ":reset":
                interp = Interpreter()
                print("interpreter reset")
            else:
                print(f"unknown command {cmd} (try :help)")
            continue

        buffer.append(line)
        source = "\n".join(buffer)
        if not source.strip():
            buffer = []
            continue
        try:
            result = interp.run(source, "<repl>")
        except BombaError as e:
            if e.incomplete and line.strip():
                continue  # wait for the rest of the block
            print(e.format(), file=sys.stderr)
        except KeyboardInterrupt:
            print("\n(interrupted)")
        else:
            if result is not None:
                print(display(result, nested=True))
        buffer = []


def main(argv=None):
    ap = argparse.ArgumentParser(prog="bomba", description="Run bomba programs.")
    ap.add_argument("file", nargs="?", help="a .bmba file to run (omit for the interactive REPL)")
    ap.add_argument("-e", "--eval", metavar="CODE", help="run CODE and exit")
    ap.add_argument("--tokens", action="store_true", help="print the tokens instead of running")
    ap.add_argument("--ast", action="store_true", help="print the syntax tree instead of running")
    ap.add_argument("--version", action="version", version=f"bomba {__version__}")
    args = ap.parse_args(argv)

    sys.setrecursionlimit(max(sys.getrecursionlimit(), 20000))

    if args.eval is not None:
        source, filename = args.eval, "<string>"
    elif args.file:
        try:
            with open(args.file, encoding="utf-8") as f:
                source = f.read()
        except OSError as e:
            print(f"bomba: cannot open {args.file}: {e.strerror}", file=sys.stderr)
            return 2
        filename = args.file
    else:
        if args.tokens or args.ast:
            source, filename = sys.stdin.read(), "<stdin>"
        else:
            return repl()

    try:
        if args.tokens:
            for t in tokenize(source):
                print(f"{t.line}:{t.col}\t{t.type}\t{t.value!r}")
            return 0
        if args.ast:
            pprint.pprint(parse(source), width=100)
            return 0
        interp = Interpreter()
        if args.file and args.eval is None:
            interp.run_file(filename)
        else:
            interp.run(source, filename)
    except BombaError as e:
        if e.filename is None:
            e.attach(filename=filename, source=source)
        print(e.format(), file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\ninterrupted", file=sys.stderr)
        return 130
    return 0


if __name__ == "__main__":
    sys.exit(main())
