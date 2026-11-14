import os
import subprocess
import sys
import unittest

from bomba import BombaError, Interpreter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXAMPLES = os.path.join(ROOT, "examples")


def run(source):
    """Run source, return (printed lines, value of last expression)."""
    out = []
    interp = Interpreter(out=out.append)
    value = interp.run(source)
    return out, value


def no_input(prompt=""):
    raise EOFError()


def value(source):
    return run(source)[1]


def output(source):
    return run(source)[0]


class TestBasics(unittest.TestCase):
    def test_numbers(self):
        self.assertEqual(value("1 + 2 * 3"), 7)
        self.assertEqual(value("(1 + 2) * 3"), 9)
        self.assertEqual(value("7 / 2"), 3.5)
        self.assertEqual(value("7 // 2"), 3)
        self.assertEqual(value("7 % 3"), 1)
        self.assertEqual(value("2 ** 3 ** 2"), 512)
        self.assertEqual(value("-2 ** 2"), -4)
        self.assertEqual(value("1_000_000"), 1000000)
        self.assertEqual(value("1.5e3"), 1500.0)

    def test_strings(self):
        self.assertEqual(value('"a" + "b"'), "ab")
        self.assertEqual(value('"ab" * 3'), "ababab")
        self.assertEqual(value('"hello"[1]'), "e")
        self.assertEqual(value('"hello"[1:3]'), "el")
        self.assertEqual(value('"tab\\there"'), "tab\there")

    def test_interpolation(self):
        self.assertEqual(value('let x = 4\n"x={x}, x*2={x * 2}"'), "x=4, x*2=8")
        self.assertEqual(value('let m = {a: [1, 2]}\n"{m.a} {len(m.a)}"'), "[1, 2] 2")
        self.assertEqual(value('"{{literal}}"'), "{literal}")
        self.assertEqual(value("'no {interpolation}'"), "no {interpolation}")
        self.assertEqual(value('"nested {"q" + "r"}"'), "nested qr")

    def test_booleans_and_nil(self):
        self.assertIs(value("true and false"), False)
        self.assertIs(value("not nil"), True)
        self.assertEqual(value('nil or "default"'), "default")
        self.assertIs(value("1 == true"), False)
        self.assertIs(value("[1, [2]] == [1, [2]]"), True)

    def test_comparisons_and_in(self):
        self.assertIs(value("3 > 2"), True)
        self.assertIs(value('"a" < "b"'), True)
        self.assertIs(value("2 in [1, 2, 3]"), True)
        self.assertIs(value('"ell" in "hello"'), True)
        self.assertIs(value('"k" in {k: 1}'), True)
        self.assertIs(value("4 not in [1, 2]"), True)


class TestVariablesAndScope(unittest.TestCase):
    def test_let_and_assign(self):
        self.assertEqual(value("let x = 1\nx = x + 1\nx += 10\nx"), 12)

    def test_assign_requires_declaration(self):
        with self.assertRaises(BombaError) as cm:
            run("y = 1")
        self.assertEqual(cm.exception.kind, "NameError")

    def test_block_scope(self):
        src = "let x = 1\nif true {\n let x = 2\n}\nx"
        self.assertEqual(value(src), 1)

    def test_inner_block_updates_outer(self):
        src = "let x = 1\nif true {\n x = 2\n}\nx"
        self.assertEqual(value(src), 2)

    def test_semicolons(self):
        self.assertEqual(value("let a = 1; let b = 2; a + b"), 3)


class TestControlFlow(unittest.TestCase):
    def test_if_elif_else(self):
        src = """
fn grade(n) {
  if n >= 90 { return "A" }
  elif n >= 70 { return "B" }
  else { return "C" }
}
[grade(95), grade(75), grade(10)]
"""
        self.assertEqual(value(src), ["A", "B", "C"])

    def test_else_if(self):
        self.assertEqual(value('let r = 0\nif false { r = 1 } else if true { r = 2 }\nr'), 2)

    def test_while_break_continue(self):
        src = """
let out = []
let i = 0
while true {
  i += 1
  if i % 2 == 0 { continue }
  if i > 7 { break }
  push(out, i)
}
out
"""
        self.assertEqual(value(src), [1, 3, 5, 7])

    def test_for_loops(self):
        self.assertEqual(value("let s = 0\nfor x in [1, 2, 3] { s += x }\ns"), 6)
        self.assertEqual(value("let r = []\nfor i, x in ['a', 'b'] { push(r, i) }\nr"), [0, 1])
        self.assertEqual(value("let r = []\nfor k, v in {a: 1, b: 2} { push(r, k + str(v)) }\nr"), ["a1", "b2"])
        self.assertEqual(value('let r = ""\nfor c in "abc" { r = c + r }\nr'), "cba")

    def test_loop_closures_capture_each_iteration(self):
        src = "let fs = []\nfor i in range(3) { push(fs, fn() => i) }\nmap(fs, fn(f) => f())"
        self.assertEqual(value(src), [0, 1, 2])


class TestFunctions(unittest.TestCase):
    def test_recursion(self):
        self.assertEqual(value("fn f(n) { if n < 2 { return n }\n return f(n-1) + f(n-2) }\nf(15)"), 610)

    def test_closure_counter(self):
        src = """
fn counter() {
  let n = 0
  return fn() {
    n += 1
    return n
  }
}
let c = counter()
c()
c()
c()
"""
        self.assertEqual(value(src), 3)

    def test_defaults_and_arrow(self):
        self.assertEqual(value('fn g(a, b = a * 2) => a + b\n[g(1), g(1, 1)]'), [3, 2])

    def test_wrong_arg_count(self):
        with self.assertRaises(BombaError) as cm:
            run("fn f(a) { return a }\nf(1, 2)")
        self.assertIn("takes 1 argument", cm.exception.message)

    def test_implicit_nil_return(self):
        self.assertIsNone(value("fn f() { let x = 1 }\nf()"))

    def test_higher_order(self):
        self.assertEqual(value("reduce(map(range(5), fn(x) => x * x), fn(a, b) => a + b)"), 30)

    def test_recursion_limit_is_a_bomba_error(self):
        with self.assertRaises(BombaError) as cm:
            run("fn f() { return f() }\nf()")
        self.assertEqual(cm.exception.kind, "RecursionError")


class TestCollections(unittest.TestCase):
    def test_list_ops(self):
        self.assertEqual(value("let a = [1, 2]\npush(a, 3)\na[0] = 9\na"), [9, 2, 3])
        self.assertEqual(value("[1, 2] + [3]"), [1, 2, 3])
        self.assertEqual(value("[0] * 3"), [0, 0, 0])
        self.assertEqual(value("[5, 1, 4][-1]"), 4)
        self.assertEqual(value("sort([3, 1, 2])"), [1, 2, 3])
        self.assertEqual(value('sort(["bb", "a", "ccc"], fn(s) => -len(s))'), ["ccc", "bb", "a"])

    def test_map_ops(self):
        self.assertEqual(value("let m = {a: 1}\nm.b = 2\nm['c'] = 3\nm.a += 10\nm"), {"a": 11, "b": 2, "c": 3})
        self.assertEqual(value("keys({x: 1, y: 2})"), ["x", "y"])
        self.assertEqual(value("get({}, 'missing', 7)"), 7)
        self.assertEqual(value("let k = 'dyn'\n{(k): 1}"), {"dyn": 1})

    def test_index_errors(self):
        for src, kind in [("[1][5]", "IndexError"), ("{a: 1}.b", "KeyError"), ("{}['x']", "KeyError"), ("5[0]", "TypeError")]:
            with self.assertRaises(BombaError) as cm:
                run(src)
            self.assertEqual(cm.exception.kind, kind, src)


class TestErrors(unittest.TestCase):
    def test_try_catch_runtime_error(self):
        src = 'let r = nil\ntry { 1 / 0 } catch e { r = e.type }\nr'
        self.assertEqual(value(src), "ZeroDivisionError")

    def test_throw_any_value(self):
        self.assertEqual(value('let r = nil\ntry { throw {code: 1} } catch e { r = e.code }\nr'), 1)

    def test_uncaught_throw(self):
        with self.assertRaises(BombaError) as cm:
            run('throw "boom"')
        self.assertEqual(cm.exception.kind, "Uncaught")
        self.assertEqual(cm.exception.message, "boom")

    def test_error_positions(self):
        with self.assertRaises(BombaError) as cm:
            run('let a = 1\nlet b = a + "x"')
        e = cm.exception
        self.assertEqual((e.kind, e.line), ("TypeError", 2))
        self.assertIn('let b = a + "x"', e.format())
        self.assertIn("^", e.format())

    def test_syntax_errors(self):
        cases = {
            "let = 3": "expected a variable name",
            "if x { ": "expected '}'",
            "return 1": "outside of a function",
            "break": "outside of a loop",
            "1 = 2": "can only assign",
            '"unterminated': "unterminated string",
            "let x = 1 2": "expected end of statement",
            "fn f(a, a) {}": "duplicate parameter",
        }
        for src, msg in cases.items():
            with self.assertRaises(BombaError, msg=src) as cm:
                run(src)
            self.assertEqual(cm.exception.kind, "SyntaxError", src)
            self.assertIn(msg, cm.exception.message, src)

    def test_incomplete_input_is_flagged(self):
        for src in ["fn f() {", "let x = (1 +", "[1, 2"]:
            with self.assertRaises(BombaError) as cm:
                run(src)
            self.assertTrue(cm.exception.incomplete, src)

    def test_type_errors(self):
        for src in ['1 + "a"', '"a" - "b"', "-[1]", "[1] < [2]", "nil()"]:
            with self.assertRaises(BombaError) as cm:
                run(src)
            self.assertEqual(cm.exception.kind, "TypeError", src)


class TestBuiltins(unittest.TestCase):
    def test_print_formatting(self):
        self.assertEqual(output('print(1, 2.5, "s", true, nil, [1, "a"], {k: "v"})'),
                         ['1 2.5 s true nil [1, "a"] {"k": "v"}'])

    def test_conversions(self):
        self.assertEqual(value('int("42") + int(3.9)'), 45)
        self.assertEqual(value('float("2.5")'), 2.5)
        self.assertEqual(value("str(12) + str(nil)"), "12nil")
        self.assertEqual(value("type(1.0)"), "float")

    def test_strings(self):
        self.assertEqual(value('split("a,b", ",")'), ["a", "b"])
        self.assertEqual(value('join([1, 2], "-")'), "1-2")
        self.assertEqual(value('upper("ab") + lower("CD") + trim("  x ")'), "ABcdx")
        self.assertEqual(value('replace("aXa", "X", "-")'), "a-a")
        self.assertEqual(value('pad(7, 3, "0") + pad("a", -3) + "|"'), "007a  |")

    def test_math(self):
        self.assertEqual(value("math.sqrt(16)"), 4.0)
        self.assertEqual(value("math.floor(2.7) + math.ceil(2.1)"), 5)
        self.assertEqual(value("min([3, 1, 2]) + max(4, 9)"), 10)
        self.assertEqual(value("round(2.567, 2)"), 2.57)

    def test_seed_is_per_interpreter(self):
        a = Interpreter(out=lambda s: None)
        a.run("math.seed(7)")
        first = a.run("math.randint(1, 1000000)")
        b = Interpreter(out=lambda s: None)
        b.run("math.seed(7)")
        self.assertEqual(b.run("math.randint(1, 1000000)"), first)
        c = Interpreter(out=lambda s: None)  # unseeded: must not continue a's sequence
        self.assertNotEqual([c.run("math.randint(1, 1000000)") for _ in range(3)],
                            [a.run("math.randint(1, 1000000)") for _ in range(3)])

    def test_builtin_arity(self):
        with self.assertRaises(BombaError) as cm:
            run("len()")
        self.assertIn("len() takes 1 argument", cm.exception.message)

    def test_guess_example_with_input(self):
        out, answers = [], ["abc", "1", "100"]

        def read(prompt=""):
            if not answers:
                raise EOFError()
            return answers.pop(0)

        interp = Interpreter(out=out.append, read=read)
        interp.run("math.seed(1)")  # seeds this interpreter only
        interp.run_file(os.path.join(EXAMPLES, "guess.bmba"))
        text = "\n".join(out)
        self.assertIn("'abc' is not a number", text)
        self.assertIn("Higher!", text)

    def test_input(self):
        interp = Interpreter(out=lambda s: None, read=lambda prompt: "Ada")
        self.assertEqual(interp.run('"hi " + input("name? ")'), "hi Ada")


class TestExamples(unittest.TestCase):
    expected = {
        "hello.bmba": "Hello, world!",
        "fizzbuzz.bmba": "FizzBuzz",
        "functions.bmba": "fib(90) = 2880067194370816120",
        "collections.bmba": "ranking: erin > alice > carol > bob > dave",
        "errors.bmba": "could not withdraw, short by 30 (INSUFFICIENT)",
        "primes.bmba": "25 primes below 100:",
        "quicksort.bmba": "matches the builtin sort()",
        "bank.bmba": "Remco has 120",
        "mandelbrot.bmba": "@@@@",
        "life.bmba": "generation 3",
        "modules.bmba": "The Bomba Programming Language",
        "brainfuck.bmba": "Hello World!",
        "tour.bmba": "That was the tour",
        "guess.bmba": "I'm thinking of a number",
    }

    def test_every_example_runs(self):
        files = sorted(f for f in os.listdir(EXAMPLES) if f.endswith(".bmba"))
        self.assertEqual(set(files), set(self.expected), "keep the expected outputs in sync with examples/")
        for name in files:
            with self.subTest(example=name):
                out = []
                Interpreter(out=out.append, read=no_input).run_file(os.path.join(EXAMPLES, name))
                self.assertIn(self.expected[name], "\n".join(out))


class TestCLI(unittest.TestCase):
    def cli(self, *args, stdin=None):
        return subprocess.run([sys.executable, "-m", "bomba", *args], input=stdin,
                              capture_output=True, text=True, cwd=ROOT)

    def test_eval(self):
        r = self.cli("-e", 'print("ok {1 + 1}")')
        self.assertEqual((r.returncode, r.stdout), (0, "ok 2\n"))

    def test_error_exit_code(self):
        r = self.cli("-e", "print(1 / 0)")
        self.assertEqual(r.returncode, 1)
        self.assertIn("ZeroDivisionError", r.stderr)

    def test_repl_multiline(self):
        r = self.cli(stdin="fn sq(x) {\n  return x * x\n}\nsq(12)\n:quit\n")
        self.assertIn("144", r.stdout)

    def test_ast_flag(self):
        r = self.cli("--ast", stdin="let x = 1\n")
        self.assertIn("Let(name='x'", r.stdout)


if __name__ == "__main__":
    unittest.main()
