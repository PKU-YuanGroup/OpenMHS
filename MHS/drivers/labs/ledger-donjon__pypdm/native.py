"""Hardware backend: opens the PDM serial link and one PDM device.

Used only with backend="hardware" and allow_hardware=True (an operator decision).  This package is model-authored and
unreviewed, and it is R2 (a model review raised it from the card's floor: a laser above class 1): the loader refuses
its hardware backend until a human signs ``reviewed_by`` in driver.lock.json, and nothing here ran.  The
acceptance gate runs the fake backend and never imports this module or the pypdm package.

Options of the backend: ``dev`` (required) is the serial device path the upstream Link opens at 125000 baud
(pypdm/pdm.py:176-186), and ``address`` (required) is the PDM address every frame carries (pypdm/pdm.py:262-269).
The PDM constructor queries the protocol version and refuses a version outside 3.4 to 3.7 (pypdm/pdm.py:278-288).
"""


def connect(dev, address):
    from pypdm.pdm import Link, PDM

    return PDM(address, Link(dev))
