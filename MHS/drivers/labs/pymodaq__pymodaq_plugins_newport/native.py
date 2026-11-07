"""Hardware backend: open the upstream SMC100 pyvisa wrapper.

The acceptance gate never imports this file; it is used only by a reviewed
deployment with ``backend="hardware"`` and ``allow_hardware=True``.  The
upstream package must be installed (the task card's ``pip install .``).
"""


def connect(port, dev_number=1, **_options):
    from pymodaq_plugins_newport.hardware.smc100 import SMC100

    return SMC100(port=port, dev_number=dev_number)
