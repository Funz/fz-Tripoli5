#!/usr/bin/env python3
"""Generate .fz/models/Tripoli5.json from tools/tripoli5_outputs.py.

Each output of the model is a ``python://`` expression (fz >= 1.2), evaluated
by fz in the case output directory without any shell: it executes the source
of one function of tools/tripoli5_outputs.py (with the helpers and constants it
uses) and calls it on the case directory ``base_dir``:

    python://(lambda g, d: (exec(SOURCE, g), g['mean_keff'](d))[1])({}, base_dir)

The parsing logic is thus written, reviewed and tested as plain Python in
tools/tripoli5_outputs.py; the JSON is a build product.

Usage (from the repository root):
    python3 tools/make_model.py           # rewrite .fz/models/Tripoli5.json
    python3 tools/make_model.py --check   # exit 1 if the JSON is not up to date
"""
import ast
import json
import sys
from collections import OrderedDict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODEL = ROOT / ".fz" / "models" / "Tripoli5.json"
SOURCE = ROOT / "tools" / "tripoli5_outputs.py"


def _definitions(tree):
    """Top-level functions and constants: name -> (node, source names it uses)."""
    defs = {}
    for node in tree.body:
        if isinstance(node, ast.FunctionDef):
            names = [node.name]
        elif isinstance(node, ast.Assign):
            names = [t.id for t in node.targets if isinstance(t, ast.Name)]
        else:
            continue
        used = {n.id for n in ast.walk(node) if isinstance(n, ast.Name)}
        for name in names:
            defs[name] = (node, used)
    return defs


def standalone_source(name, text):
    """Source of the imports, then of `name` and everything it uses, in module order."""
    tree = ast.parse(text)
    defs = _definitions(tree)
    needed, todo = set(), [name]
    while todo:
        current = todo.pop()
        if current in needed or current not in defs:
            continue
        needed.add(current)
        todo.extend(defs[current][1])
    parts = []
    for node in tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            parts.append(ast.get_source_segment(text, node))
        elif node in [defs[n][0] for n in needed]:
            segment = ast.get_source_segment(text, node)
            if isinstance(node, ast.FunctionDef):
                # docstrings are kept in tools/tripoli5_outputs.py only
                body = node.body[0]
                if isinstance(body, ast.Expr) and isinstance(body.value, ast.Constant):
                    doc = ast.get_source_segment(text, body)
                    segment = segment.replace("    " + doc + "\n", "", 1)
            parts.append(segment)
    return "\n".join(parts) + "\n"


def build():
    text = SOURCE.read_text()
    namespace = {}
    exec(compile(text, str(SOURCE), "exec"), namespace)
    outputs = OrderedDict()
    for name in namespace["OUTPUTS"]:
        src = standalone_source(name, text)
        outputs[name] = "python://(lambda g, d: (exec(%r, g), g[%r](d))[1])({}, base_dir)" % (src, name)
    return OrderedDict([
        ("id", "Tripoli5"),
        ("varprefix", "$"),
        ("formulaprefix", "@"),
        ("delim", "{}"),
        ("commentline", "#"),
        ("output", outputs),
    ])


def text():
    return json.dumps(build(), indent=4, ensure_ascii=False) + "\n"


if __name__ == "__main__":
    if "--check" in sys.argv[1:]:
        if MODEL.read_text() != text():
            sys.exit(f"{MODEL} is not up to date: run python3 tools/make_model.py")
    else:
        MODEL.write_text(text())
