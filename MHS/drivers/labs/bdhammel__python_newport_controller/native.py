"""Hardware backend: open a New Focus Picomotor controller through the upstream newport.Controller.

Used only with backend="hardware" and allow_hardware=True (an operator decision).  The gate never imports this
module or the upstream code, and no hardware was run while authoring this package.

The upstream clone is a single module ``newport.py`` at the clone root and has no packaging: the README launches it
as a script (``python newport.py``, README.md:32).  Put the clone root on PYTHONPATH before using this backend.

``connect`` needs both ids the upstream constructor requires (newport.py:65-76): ``idProduct`` and ``idVendor``.
They have no default here because the attached controller may be a different model; the README shows the 8742
product 0x4000 and vendor 0x104d only as an example (README.md:65-66).  Values may be ints or strings such as
"0x4000".  The upstream constructor raises ValueError when usb.core.find() finds no matching device
(newport.py:90-96).

This package is R1, so the loader's ``review_required`` refusal for unreviewed model-authored R2/R3 packages does not
apply here.  Nothing in the SDK protects an R1 hardware backend from an unreviewed package: a human must review this
file and the unit's safety before anyone runs it.
"""


def _usb_id(value):
    """A USB id as an int; accept an int or a string such as "0x4000" (README.md:87-90)."""
    if isinstance(value, str):
        return int(value.strip(), 0)
    return int(value)


def connect(idProduct, idVendor):
    from newport import Controller

    return Controller(idProduct=_usb_id(idProduct), idVendor=_usb_id(idVendor))
