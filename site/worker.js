// Runs bomba inside Pyodide, off the main thread, so a slow or endless
// program never freezes the page (the page can simply terminate this worker).
// Must be started as a module worker: Pyodide no longer supports classic workers.
const PYODIDE = "https://cdn.jsdelivr.net/npm/pyodide@314.0.8/";
import { loadPyodide } from "https://cdn.jsdelivr.net/npm/pyodide@314.0.8/pyodide.mjs";

const GLUE = `
import json
from bomba import Interpreter, BombaError, __version__

def run_program(source, stdin_lines, emit):
    lines = list(stdin_lines)
    def read(prompt=""):
        if prompt:
            emit(prompt, "prompt")
        if not lines:
            raise EOFError()
        value = lines.pop(0)
        emit(value, "echo")
        return value
    interp = Interpreter(out=lambda text: emit(text, "out"), read=read, max_depth=180)
    try:
        interp.run(source, "playground.bmba")
        return None
    except BombaError as e:
        return e.format()
    except RecursionError:
        return "RecursionError: program nested too deeply for the browser"
`;

let ready = (async () => {
  const pyodide = await loadPyodide({ indexURL: PYODIDE });
  const bundle = await (await fetch("bundle.json")).json();
  const fs = pyodide.FS;
  fs.mkdirTree("/home/pyodide/bomba");
  for (const [name, src] of Object.entries(bundle.modules)) {
    fs.writeFile("/home/pyodide/bomba/" + name, src);
  }
  // examples on disk so `import "lib/text"` works from the playground
  for (const ex of bundle.examples) {
    const path = "/home/pyodide/examples/" + ex.path;
    fs.mkdirTree(path.substring(0, path.lastIndexOf("/")));
    fs.writeFile(path, ex.source);
  }
  pyodide.runPython(`
import os, sys
sys.path.insert(0, "/home/pyodide")
sys.setrecursionlimit(3000)
os.chdir("/home/pyodide/examples")
`);
  pyodide.runPython(GLUE);
  const version = pyodide.runPython("__version__");
  postMessage({ type: "ready", version });
  return pyodide;
})().catch((e) => {
  postMessage({ type: "fatal", message: String(e) });
});

onmessage = async (event) => {
  const { source, stdin } = event.data;
  const pyodide = await ready;
  if (!pyodide) return;
  const run = pyodide.globals.get("run_program");
  const emit = (text, kind) => postMessage({ type: "output", text, kind });
  const started = performance.now();
  try {
    const error = run(source, pyodide.toPy(stdin), emit);
    postMessage({ type: "done", error: error ?? null, ms: performance.now() - started });
  } catch (e) {
    postMessage({ type: "done", error: String(e), ms: performance.now() - started });
  } finally {
    run.destroy();
  }
};
