"""Build the browser playground into ./_site (used by the Pages workflow).

    python scripts/build_site.py [output-dir]
"""

import json
import os
import shutil
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Order of the examples in the playground's picker.
FEATURED = ["tour", "hello", "functions", "collections", "errors", "fizzbuzz", "primes",
            "quicksort", "bank", "guess", "mandelbrot", "life", "brainfuck", "modules"]

# Pre-filled lines for the playground's input box.
STDIN = {"guess": "50\n25\n75\n37\n62\n12\n88\n43\n56"}


def main(out_dir):
    if os.path.exists(out_dir):
        shutil.rmtree(out_dir)
    os.makedirs(out_dir)

    modules = {}
    pkg = os.path.join(ROOT, "bomba")
    for name in sorted(os.listdir(pkg)):
        if name.endswith(".py"):
            with open(os.path.join(pkg, name), encoding="utf-8") as f:
                modules[name] = f.read()

    examples = []
    ex_dir = os.path.join(ROOT, "examples")
    for dirpath, _, files in os.walk(ex_dir):
        for name in files:
            if name.endswith(".bmba"):
                full = os.path.join(dirpath, name)
                rel = os.path.relpath(full, ex_dir).replace(os.sep, "/")
                with open(full, encoding="utf-8") as f:
                    ex = {"path": rel, "name": rel[:-5], "source": f.read()}
                if ex["name"] in STDIN:
                    ex["stdin"] = STDIN[ex["name"]]
                examples.append(ex)

    def order(ex):
        n = ex["name"]
        return (FEATURED.index(n) if n in FEATURED else len(FEATURED), n)

    examples.sort(key=order)

    with open(os.path.join(out_dir, "bundle.json"), "w", encoding="utf-8") as f:
        json.dump({"modules": modules, "examples": examples}, f)
    for name in ("index.html", "worker.js"):
        shutil.copy(os.path.join(ROOT, "site", name), out_dir)
    open(os.path.join(out_dir, ".nojekyll"), "w").close()
    print(f"built {out_dir}: {len(modules)} modules, {len(examples)} examples")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "_site"))
