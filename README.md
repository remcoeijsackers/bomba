# bomba

**A small, friendly scripting language** with closures, lists and maps, string interpolation,
error handling and modules, implemented as a tree-walking interpreter in pure Python with no dependencies.

**[▶ Try it in your browser](https://remcoeijsackers.github.io/bomba/)**: the playground runs the real interpreter through WebAssembly.

```bmba
fn make_counter(start = 0) {
  let count = start
  return fn() {
    count += 1
    return count
  }
}

let next = make_counter()
next()
print("counted to {next()}")                 # counted to 2

let squares = map(range(1, 6), fn(x) => x * x)
print(squares, "sum:", sum(squares))        # [1, 4, 9, 16, 25] sum: 55

try {
  print(1 / 0)
} catch e {
  print("caught {e.type}: {e.message}")     # caught ZeroDivisionError: division by zero
}
```

## Getting started

You need Python 3.10 or newer. There is nothing else to install.

```sh
git clone https://github.com/remcoeijsackers/bomba
cd bomba
python -m bomba examples/tour.bmba   # run a program
python -m bomba                      # interactive REPL
python -m bomba -e 'print(2 ** 64)'  # one-liner
```

Or install it as a command:

```sh
pip install .
bomba examples/mandelbrot.bmba
```

The REPL accepts multi-line blocks: it waits until every `{` is closed. Results of
expressions are shown automatically, and `:vars`, `:reset` and `:quit` do what you expect.

```
$ bomba
bomba 1.0.0 — type :help for help, :quit to leave
bomba> fn sq(x) {
...   return x * x
... }
bomba> map([1, 2, 3], sq)
[1, 4, 9]
```

## The language

### Values

| Type       | Examples                              |
|------------|---------------------------------------|
| `int`      | `42`, `-7`, `1_000_000`               |
| `float`    | `3.14`, `1.5e3`                       |
| `string`   | `"hello {name}"`, `'raw {braces}'`    |
| `bool`     | `true`, `false`                       |
| `nil`      | `nil`                                 |
| `list`     | `[1, "two", [3]]`                     |
| `map`      | `{name: "Ada", "key with space": 1}`  |
| `function` | `fn(x) => x * 2`                      |

`false`, `nil`, `0`, `""`, `[]` and `{}` are falsy. Everything else is truthy.

### Variables

```bmba
let x = 10        # declare
x = x + 1         # reassign (must be declared first)
x += 5            # also -=, *=, /=, //=, %=
```

Every `{ }` block has its own scope. Inner blocks can read and update outer variables, and a
`let` inside a block shadows a variable of the same name.

### Strings

Double-quoted strings interpolate any expression between `{ }`. Single-quoted strings don't.

```bmba
let name = "bomba"
print("{name} has {len(name)} letters")   # bomba has 5 letters
print('{name}')                           # {name}
print("{{literal braces}}")               # {literal braces}
print("abc"[0], "abcdef"[1:3], "ab" * 3)  # a bc ababab
```

Escape sequences: `\n`, `\t`, `\r`, `\\`, `\"`, `\'`, `\{`, `\}`.

### Operators

| Precedence (low → high) | Operators                                   |
|-------------------------|---------------------------------------------|
| logical                 | `or`, `and`, `not`                          |
| comparison              | `==` `!=` `<` `<=` `>` `>=` `in` `not in`   |
| additive                | `+` `-`                                     |
| multiplicative          | `*` `/` `//` `%`                            |
| unary                   | `-x`                                        |
| power (right-assoc.)    | `**`                                        |
| postfix                 | `f(x)` `xs[i]` `xs[a:b]` `m.field`          |

`/` always gives a float and `//` is floor division. `+` joins strings, lists and maps.
`and`/`or` short-circuit and return one of their operands, so `name or "anonymous"` works.
`==` compares lists and maps by value, and `1 == true` is `false`.

### Control flow

```bmba
if score >= 90 {
  print("A")
} elif score >= 70 {      # "else if" works too
  print("B")
} else {
  print("C")
}

while running { ... }

for item in [1, 2, 3] { ... }
for i, item in ["a", "b"] { ... }   # index and value
for key in scores { ... }           # map keys
for key, value in scores { ... }    # map entries
for char in "hello" { ... }
```

`break` and `continue` work in both loops. Statements end at a newline, and `;` can put several
on one line. Inside `( )` and `[ ]` you can break lines freely.

### Functions

```bmba
fn area(w, h = w) {           # default values can use earlier parameters
  return w * h
}
let double = fn(x) => x * 2   # arrow functions return a single expression
fn twice(f, x) => f(f(x))

print(area(3), area(3, 4), twice(double, 5))   # 9 12 20
```

Functions are values. They can be passed around, returned and stored in lists and maps, and they
close over the variables around them. Loop variables are fresh on every iteration, so closures
created in a loop each see their own value.

### Lists and maps

```bmba
let xs = [3, 1, 2]
push(xs, 4)
xs[0] = 10
print(xs[-1], xs[1:3], len(xs), sort(xs))

let car = {brand: "Porsche", year: 1964}   # bare names are string keys
car.colour = "silver"                     # .field is shorthand for ["field"]
car["model"] = "911"
let key = "year"
print(car[key], {(key): 1})               # (expr) as key uses its value
print(get(car, "price", "unknown"))       # default when the key is missing
```

Maps keep insertion order. Maps and closures together give you simple objects, as
[`examples/bank.bmba`](examples/bank.bmba) shows.

### Errors

Runtime errors and thrown values can be caught. A runtime error arrives as a map with
`type`, `message` and `line`. A thrown value arrives exactly as it was thrown.

```bmba
try {
  let x = [1, 2, 3][10]
} catch e {
  print(e.type, e.message)          # IndexError index 10 out of range for list of length 3
}

try {
  throw {code: 404, reason: "not found"}
} catch err {
  print(err.code)                   # 404
}
```

Uncaught errors point at the exact spot:

```
  File "demo.bmba", line 2, column 11
    let b = a + "x"
              ^
TypeError: cannot add int and string (tip: use str() or "{...}" interpolation)
```

### Modules

```bmba
import "lib/text"     # runs lib/text.bmba (relative to this file) once
print(title("hello world"))
```

## Built-in functions

| Category    | Functions |
|-------------|-----------|
| I/O         | `print(...)`, `input(prompt)` (returns `nil` at end of input) |
| Types       | `type`, `str`, `repr`, `int`, `float`, `bool`, `len` |
| Lists       | `range`, `push`, `pop`, `insert`, `remove`, `index_of`, `reverse`, `sort(list, key?)`, `zip`, `copy` |
| Functional  | `map`, `filter`, `reduce`, `any`, `all` |
| Numbers     | `abs`, `round`, `min`, `max`, `sum` |
| Maps        | `keys`, `values`, `items`, `get(map, key, default)`, `remove` |
| Strings     | `split`, `join`, `upper`, `lower`, `trim`, `replace`, `starts_with`, `ends_with`, `pad`, `chr`, `ord` |
| Misc        | `assert(cond, message)`, `clock()` |
| `math`      | `math.pi`, `math.e`, `math.inf`, `sqrt`, `floor`, `ceil`, `sin`, `cos`, `tan`, `atan2`, `log`, `log10`, `exp`, `pow`, `hypot`, `random`, `randint`, `seed` |

## Examples

| File | What it shows |
|------|---------------|
| [`tour.bmba`](examples/tour.bmba) | A guided tour of the whole language |
| [`functions.bmba`](examples/functions.bmba) | Recursion, closures, defaults, composition, memoisation |
| [`collections.bmba`](examples/collections.bmba) | Lists, maps, word counts, nested data |
| [`errors.bmba`](examples/errors.bmba) | `try`/`catch`/`throw` |
| [`bank.bmba`](examples/bank.bmba) | Objects built from maps and closures |
| [`quicksort.bmba`](examples/quicksort.bmba), [`primes.bmba`](examples/primes.bmba) | Classic algorithms |
| [`guess.bmba`](examples/guess.bmba) | An interactive game with `input()` |
| [`mandelbrot.bmba`](examples/mandelbrot.bmba) | ASCII-art Mandelbrot set |
| [`life.bmba`](examples/life.bmba) | Conway's Game of Life |
| [`brainfuck.bmba`](examples/brainfuck.bmba) | A Brainfuck interpreter written in bomba |
| [`modules.bmba`](examples/modules.bmba) | Splitting code over files with `import` |

## How it works

```
source ──► lexer ──► tokens ──► parser ──► syntax tree ──► interpreter ──► output
           lexer.py             parser.py   nodes.py         interpreter.py
                                                             builtins.py, values.py
```

- **Lexer** (`bomba/lexer.py`) turns text into tokens. Newlines end statements except inside
  `( )` and `[ ]`. String interpolation is split into literal parts and expression sources here.
- **Parser** (`bomba/parser.py`) is a hand-written recursive-descent parser. The grammar is in its
  docstring. It reports syntax errors with positions and flags incomplete input for the REPL.
- **Interpreter** (`bomba/interpreter.py`) walks the tree with environments chained for lexical
  scope. `return`, `break` and `continue` unwind with internal signals. Errors get the position of
  the innermost node that was running when they happened.

Use `python -m bomba --tokens file.bmba` or `--ast` to see the first two stages for yourself.

## Development

```sh
python -m unittest discover -s tests     # run the test suite
python scripts/build_site.py             # build the playground into _site/
```

CI runs the tests and every example on Python 3.10 to 3.13. Every push to `master` redeploys the
playground to GitHub Pages.

## License

[MIT](LICENSE)
