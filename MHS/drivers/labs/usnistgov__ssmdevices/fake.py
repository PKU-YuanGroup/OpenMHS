"""Fake backend of the Mini-Circuits RCDAT driver: an in-memory stand-in for the upstream attenuator class.

Gate G7: every public attribute defined here exists on ``ssmdevices.instruments.attenuators:MiniCircuitsRCDAT`` or on
one of its clone-side base classes in ``_minicircuits_usb.py``: ``attenuation_setting`` (attenuators.py:55-88),
``model`` and ``serial_number`` (_minicircuits_usb.py:241-249), and ``open``/``close`` (_minicircuits_usb.py:35-54).
The quarter-decibel quantization of the setter copies the upstream encoder, which sends the whole-decibel part and
the quarter-decibel part (attenuators.py:79-85).  Every fixed value below is test data, marked ``# placeholder``; none
is a Fact, a Limit or a statement about a real attenuator.  Nothing here talks to a device.
"""


class FakeMiniCircuitsRCDAT:
    def __init__(self, **_options):
        self._attenuation = 0.0              # placeholder: start at zero attenuation
        self._part_number = "RCDAT-0000"     # placeholder
        self._serial_number = "00000000000"  # placeholder
        self._open = False

    @property
    def attenuation_setting(self):
        return self._attenuation

    @attenuation_setting.setter
    def attenuation_setting(self, value):
        # The upstream encoder keeps the whole-decibel part and a quarter-decibel part (attenuators.py:79-85).
        whole = int(float(value))
        quarter = int((float(value) - whole) * 4.0)
        self._attenuation = whole + quarter / 4.0

    @property
    def model(self):
        return self._part_number

    @property
    def serial_number(self):
        return self._serial_number

    def open(self):
        self._open = True

    def close(self):
        self._open = False
