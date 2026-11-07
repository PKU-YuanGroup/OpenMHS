"""Hardware backend: open a Prior ProScan III stage through the pinned upstream PriorStage class.

The factory imports the clone only when the hardware backend is opened; the acceptance gate runs the fake backend
and never imports this module or the upstream package.  The upstream is not an installable package.  Its own
scripts run from ``app/hardware_control/`` and import ``PriorStage`` from a top-level ``proscan`` module
(move_stage_tester.py:1-4, app.py:3), and proscan.py imports ``BaseStage`` from a top-level ``base_stage`` module
after appending the parent of its own folder to ``sys.path`` (proscan.py:6-14).  That parent held base_stage.py in
the layout the README describes (``hardware_control/prior_stage/proscan.py`` beside
``hardware_control/base_stage.py``, README.md:11-21); at the pin both files are in ``app/hardware_control/``, so
the appended ``app/`` holds no base_stage.py.  Importing the clone as ``app.hardware_control.proscan`` with only the
clone root on ``sys.path`` therefore fails with ``No module named 'base_stage'`` (the model reviewer reproduced it
on stand-in files that copy only those import lines, 2026-11-05).  This factory puts ``app/hardware_control/``
itself on ``sys.path``, appended so that the clone's generic module names (``app``, ``proscan``, ``base_stage``)
never shadow a module the host already resolves, and refuses to go on when ``proscan`` or ``base_stage`` would be
loaded from anywhere else.

``port`` is the serial port of the controller (for example the COM4 of the upstream test script,
move_stage_tester.py:10).  ``clone_root`` optionally names the pinned clone; by default it is read from the
package's task.json ``local_path`` below the repository root.  The upstream constructor takes only a port, so any
other backend option is refused rather than silently ignored.  Constructing PriorStage opens the serial port and
sends the ``?`` query of the connection handshake (proscan.py:25-56); nothing else is sent before a move.

The upstream prints the goal of every move, every reply and the result of close() with print()
(proscan.py:84, 172, 184, 186); an MHS server that talks over standard input and output would receive those lines
in its protocol stream.  This factory does not redirect them.

This package is R1, so the loader's model-authored review refusal at R2/R3 does not apply to it.  It is still
blocked: the upstream class has no stop, abort or position query, and close() only closes the serial connection
(proscan.py:180-186).  The e-stop reports SAFE_STATE_UNREACHED.  This factory has never run against the upstream
clone or a controller, no hardware was attached, and the package is model-authored and unreviewed (reviewed_by is
null).
"""

import importlib
import importlib.util
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCE_DIR = ("app", "hardware_control")
MODULE = "proscan"
BASE_MODULE = "base_stage"


def _default_clone_root():
    card = json.loads((HERE / "task.json").read_text(encoding="utf-8"))
    local_path = card.get("local_path")
    if not isinstance(local_path, str) or not local_path:
        raise RuntimeError("task.json has no local_path for the pinned upstream clone")
    root = HERE.parents[3] / local_path
    if not root.is_dir():
        raise FileNotFoundError(f"the pinned upstream clone is not at {root}")
    return root


def _origin(name):
    """Where ``name`` would be (or was) loaded from, without importing it."""
    spec = importlib.util.find_spec(name)
    if spec is None or not spec.origin:
        return None
    return Path(spec.origin).resolve()


def connect(port, clone_root=None):
    """Open the pinned PriorStage on ``port``; ``clone_root`` overrides the task.json location."""
    if clone_root is not None:
        root = Path(clone_root).expanduser().resolve()
    else:
        root = _default_clone_root().resolve()
    source = root.joinpath(*SOURCE_DIR).resolve()
    for name in (BASE_MODULE, MODULE):
        if not (source / f"{name}.py").is_file():
            raise FileNotFoundError(f"{name}.py of the pinned clone is not in {source}")
    if str(source) not in sys.path:
        sys.path.append(str(source))
    for name in (BASE_MODULE, MODULE):
        expected = (source / f"{name}.py").resolve()
        found = _origin(name)
        if found != expected:
            raise RuntimeError(f"module {name!r} resolves to {found}, not to the pinned clone's {expected}; "
                               "another module of that name is importable in this process")
    module = importlib.import_module(MODULE)
    return module.PriorStage(port)
