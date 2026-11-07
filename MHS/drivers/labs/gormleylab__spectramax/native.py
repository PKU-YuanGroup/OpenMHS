"""Hardware backend: open a SpectraMax reader through the upstream SoftMax Pro wrapper.

Used only with backend="hardware" and allow_hardware=True (an operator decision).  This package is model-authored
and unreviewed, and it is R2: the loader refuses its hardware backend until a human signs ``reviewed_by`` in
driver.lock.json.  The acceptance gate runs the fake backend and never imports this module or the upstream package.

Options of the backend: ``server`` (default "localhost") and ``port`` (default 9000) are the arguments of the
upstream constructor (spectramax.py:47-56); initialize() then connects the SMPAutomationClient
(spectramax.py:66-94).  The upstream module requires pythonnet and the SoftMax Pro 7.0 Automation SDK
(README.md:17-39), so this factory only works on a Windows installation where both are present.
"""


def connect(server="localhost", port=9000, **_options):
    from spectramax import Spectramax

    device = Spectramax(server=server, port=port)
    if not device.initialize():
        raise RuntimeError("SoftMax Pro automation client did not initialize")
    return device
