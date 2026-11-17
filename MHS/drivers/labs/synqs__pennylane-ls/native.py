"""Hardware backend: opens the SYNQS single-qudit device through the pinned upstream class.

Used only with ``backend="hardware"`` by an operator.  The package is model-authored and unreviewed, and this driver
is R2, so the loader refuses its hardware backend until a human signs ``reviewed_by`` in driver.lock.json.  The
acceptance gate runs the fake backend and never imports this module or the ``pennylane_ls`` package.

Deployment must install the pinned clone (``pip install .``) with ``pennylane==0.20.0`` and ``requests==2.26.0``
(requirements.txt:1-5), and must put the control server reachable at ``url``.  The default URL of the upstream class
is the qsimsim hardware simulator (single_qudit_device.py:44); real hardware is the labscript-qc server (README.md:37).
The package does not run the hardware path and makes no claim about a live server.
"""


def connect(url, username=None, password=None, shots=1, blocking=True, **options):
    """Construct the pinned upstream SingleQuditDevice for the operator's control server."""
    from pennylane_ls.single_qudit_device import SingleQuditDevice

    return SingleQuditDevice(url=url, username=username, password=password, shots=shots,
                             blocking=blocking, **options)
