"""Hardware backend: opens the BASF pyTEM interface over the Thermo Fisher TEMScripting COM objects.

Used only with backend="hardware" and allow_hardware=True (an operator decision).  This package is model-authored and
unreviewed, and it is R3: the loader refuses its hardware backend until a human signs ``reviewed_by`` in
driver.lock.json (the loader does this at R2 and R3 only; an R0 or R1 package must not claim it).  The acceptance gate
runs the fake backend and never imports this module or the pyTEM package.

The upstream Interface constructor takes no options: it creates ``TEMScripting.Instrument`` and
``TEMAdvancedScripting.AdvancedInstrument`` through comtypes and reads the current stage position
(pyTEM/Interface.py:77-98).  comtypes drives Windows COM and the card's install block names platform windows; the
Thermo Fisher scripting interfaces must be installed on the microscope control computer (README.md:16-18).
``connect`` therefore accepts no transport options and passes none to the upstream class.
"""


def connect(**_options):
    from pyTEM.Interface import Interface

    return Interface()
