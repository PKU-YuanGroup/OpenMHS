"""Hardware backend: opens a Mini-Circuits RCDAT USB switch attenuator through the upstream class.

Used only with backend="hardware" and allow_hardware=True (an operator decision).  This package is model-authored,
unreviewed and R1, so the loader's refusal of an unreviewed model-written hardware backend (it applies at R2 and R3
only) does not protect this package; do not open this backend before a human review.

``resource`` is the attenuator serial number the upstream class looks for when more than one Mini-Circuits device
is attached (_minicircuits_usb.py:20-24).  With ``resource=None`` the upstream class accepts a single attached
device (_minicircuits_usb.py:155-162).  The other keyword options go to the upstream constructor: ``frequency``,
``output_power_offset``, ``calibration_path``, ``channel``, ``usb_path`` and ``timeout`` (attenuators.py:17-49,
_minicircuits_usb.py:27-33).  The factory opens the HID device before returning it.

The acceptance gate runs the fake backend and never imports this module or the upstream ``ssmdevices`` package.
"""


def connect(resource=None, **options):
    from ssmdevices.instruments.attenuators import MiniCircuitsRCDAT

    device = MiniCircuitsRCDAT(resource, **options)
    device.open()       # _minicircuits_usb.py:35-43
    return device
