"""Hardware backend: open the upstream ``biped_controller:BipedController``.

Used only with backend="hardware" and allow_hardware=True (an operator decision).  This package is model-authored,
unreviewed and R2: the loader refuses its hardware backend until a human signs ``reviewed_by`` in driver.lock.json.
The acceptance gate runs the fake backend and never imports this module or the clone; nothing here ran on a robot.

The clone is a script bundle, not an installed package.  ``biped_controller.py`` at the clone root imports
``motor_controller``, ``sensor_controller``, ``publisher`` and ``numpy_ringbuffer``, and ``motor_controller`` imports
``build.ethercat_motor_py`` (motor_controller.py:11), so the pybind extension must be built first (README.md:105-120)
and the clone root must be importable.  ``motor_controller`` opens ``motor_config.yaml`` in the working directory
(motor_controller.py:67-70) and ``biped_controller`` loads ``checkpoint/baseline`` relative to the working directory
(biped_controller.py:34-44).  Start the endpoint from the clone root (or pass ``workdir``), after running the
initialization of README.md:172-182 once.

Options: ``clone_root`` is the clone directory (default: ``local_path`` of this package's task.json, resolved from
the repository root); ``workdir`` is the working directory (default: the clone root).  BipedController takes no
constructor options, so any other option is refused.
"""

import json
import os
import sys
from pathlib import Path


def _default_clone_root() -> Path:
    package = Path(__file__).resolve().parent
    card = json.loads((package / "task.json").read_text(encoding="utf-8"))
    return (package.parents[3] / str(card["local_path"])).resolve()


def connect(clone_root=None, workdir=None, **options):
    """Open the upstream BipedController from the pinned clone."""
    if options:
        raise TypeError(f"unknown Duke Humanoid hardware options: {sorted(options)}")
    root = Path(clone_root).expanduser().resolve() if clone_root is not None else _default_clone_root()
    if not (root / "biped_controller.py").is_file():
        raise RuntimeError(f"{root} does not contain biped_controller.py; pass clone_root")
    if not any((root / "build").glob("ethercat_motor_py*")):
        raise RuntimeError(f"{root}/build has no ethercat_motor_py extension; build it as README.md:105-120 describes")
    cwd = Path(workdir).expanduser().resolve() if workdir is not None else root
    if not (cwd / "motor_config.yaml").is_file():
        raise RuntimeError(f"{cwd}/motor_config.yaml is missing; run motor_controller.py once from the clone root to "
                           "initialize the joint offsets (README.md:172-182)")
    os.chdir(cwd)
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    from biped_controller import BipedController

    return BipedController()
