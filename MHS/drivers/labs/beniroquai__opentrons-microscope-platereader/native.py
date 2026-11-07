"""Hardware backend: open the NEJE laser 2 controller through the upstream pyGraver class.

Used only with backend="hardware" and allow_hardware=True (an operator decision).  This package is model-authored
and unreviewed, and it is R3: the loader refuses its hardware backend until a human signs ``reviewed_by`` in
driver.lock.json.  The acceptance gate runs the fake backend and never imports this module or the upstream clone;
nothing here ran on hardware.

The upstream file is a script rather than an importable module: after the class it opens ``pyGraver("COM7")`` and
runs a 10 by 10 move loop at module level (PYTHON/opentrons_neje_laser2_controler.py:239-257).  Importing the file
would therefore open a serial port during import.  This factory parses the file and executes only its imports, the
two MAX_* constants and the ``pyGraver`` class definition, so the hardware path uses the upstream class itself
without running the module-level test block.

Options of the backend: ``port`` (required) is the serial port of the controller; the upstream class fixes the baud
rate at 57600 (PYTHON/opentrons_neje_laser2_controler.py:32).  ``source`` optionally overrides the path of the
upstream file.
"""

import ast
from pathlib import Path

DEFAULT_SOURCE = (Path(__file__).resolve().parents[4] / "labs" / "beniroquai"
                  / "opentrons-microscope-platereader" / "PYTHON" / "opentrons_neje_laser2_controler.py")
CONSTANTS = ("MAX_WIDTH", "MAX_HEIGHT")


def _class_definition(source):
    tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
    body = []
    for node in tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            body.append(node)
        elif isinstance(node, ast.Assign) and any(
                isinstance(target, ast.Name) and target.id in CONSTANTS for target in node.targets):

            body.append(node)
        elif isinstance(node, ast.ClassDef) and node.name == "pyGraver":
            body.append(node)
    if not any(isinstance(node, ast.ClassDef) and node.name == "pyGraver" for node in body):
        raise RuntimeError(f"pyGraver is not defined in {source}")
    module = ast.Module(body=body, type_ignores=[])
    ast.fix_missing_locations(module)
    namespace = {"__name__": "opentrons_neje_laser2_controler"}
    exec(compile(module, str(source), "exec"), namespace)
    return namespace["pyGraver"]


def connect(port, **options):
    source = Path(options.get("source") or DEFAULT_SOURCE)
    controller = _class_definition(source)
    return controller(port=port)
