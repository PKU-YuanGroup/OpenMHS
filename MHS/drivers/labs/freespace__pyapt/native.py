"""Hardware backend: opens a Thorlabs APT stage controller through the upstream pyAPT classes.

Used only with backend="hardware" and allow_hardware=True (an operator decision).  This package is model-authored
and unreviewed and no hardware was attached or run.  It is R1, so the loader's refusal of an unreviewed model-written
package applies only at R2 and R3 and does not protect this backend; a human must review the package before any
hardware use.  The acceptance gate runs the fake backend and never imports this module or the pyAPT package.

The deployment option ``stage`` selects the upstream subclass and is required: ``MTS50`` (pyAPT/mts50.py:4), ``PRM1``
(pyAPT/prm1.py:4) or ``LTS300`` (pyAPT/lts300.py:4).  ``serial_number`` selects the FTDI device of that controller
(pyAPT/controller.py:18-27); other options are passed to the Controller constructor.
"""


def connect(serial_number=None, stage=None, label=None, **_options):
    from pyAPT.lts300 import LTS300
    from pyAPT.mts50 import MTS50
    from pyAPT.prm1 import PRM1

    classes = {"MTS50": MTS50, "PRM1": PRM1, "LTS300": LTS300}
    if stage not in classes:
        raise ValueError(f"stage must be one of {sorted(classes)}, got {stage!r}")
    return classes[stage](serial_number=serial_number, label=label)
