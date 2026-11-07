"""Fake backend of the PM100D driver: a source-shaped stand-in for the QCoDeS Thorlab_PM100D instrument.

The upstream ``__init__`` stores one QCoDeS Parameter per measurement in an instance attribute (PM100D.py:41-151).
This fake stores one ``_FakeParameter`` under each bound attribute name and implements only the calls the driver
makes: ``Parameter.get()``, ``Parameter.set(value)`` for the two settable Parameters, and the instrument's
``write(cmd)`` and ``close()``, which the upstream class inherits from QCoDeS ``VisaInstrument``.  Values are what the
upstream Parameter returns after its parsers: floats for the float-parsed and the power reads, a bool for the on/off
mapping, and the raw reply string for ``averaging``, which declares no parser.

Nothing here imports QCoDeS or PyVISA, opens a VISA session or talks to a meter.  The fake keeps every command it
was sent in ``_written`` (the stop test reads it).  Every value is a placeholder chosen for the tests, not a fact about
a PM100D or a sensor head.

Fidelity gap: ``_FakeParameter.set`` stores any value.  The upstream validators (``auto_range``: ``vals.Ints(0, 1)``
with an on/off ``val_mapping``; ``power_range``: ``vals.Numbers()``), the ``val_mapping`` itself and the ``set_parser``
(PM100D.py:82-102) are not exercised, so the boolean write path through a real ``Parameter.set`` is shown only on a
stand-in.  A first supervised run must write ``auto_range`` both ways and read it back.
"""


class _FakeParameter:
    """One QCoDeS Parameter: ``get`` returns the stored value; ``set`` stores a new one when the Parameter has a
    set_cmd upstream."""

    def __init__(self, value, *, settable=False):
        self._value = value
        self._settable = settable

    def get(self):
        return self._value

    def set(self, value):
        if not self._settable:
            raise NotImplementedError("this Parameter has no set_cmd upstream")
        self._value = value


class FakeThorlabPM100D:
    def __init__(self, **_options):
        self._written = []
        self._closed = False
        self.power = _FakeParameter(1.25e-3)                             # placeholder, W
        self.power_range = _FakeParameter(2.0e-3, settable=True)         # placeholder, W
        self.auto_range = _FakeParameter(True, settable=True)            # placeholder
        self.attenuation = _FakeParameter(0.0)                           # placeholder, dB
        self.averaging = _FakeParameter("1")                             # placeholder raw AVER? reply
        self.zero_value = _FakeParameter(2.0e-9)                         # placeholder, W
        self.current_range = _FakeParameter(1.0e-5)                      # placeholder, A

    def write(self, cmd):
        """QCoDeS Instrument.write: send one command line, no reply."""
        self._written.append(cmd)

    def close(self):
        """QCoDeS Instrument.close: close the VISA session."""
        self._closed = True
