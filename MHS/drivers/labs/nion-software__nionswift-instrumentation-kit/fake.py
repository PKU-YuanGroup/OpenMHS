"""Fake backend of the Nion instrument driver: an in-memory stand-in for InstrumentDevice:Instrument.

Gate G7: the two public methods here, ``GetVal`` and ``SetVal``, are methods of
``nion.device_kit.InstrumentDevice:Instrument`` (nion/device_kit/InstrumentDevice.py:196-206).  GetVal reads a
named control through the value manager and SetVal writes it, so the fake keeps a dictionary of controls and
mirrors those signatures: ``GetVal(name, default_value=None)`` and ``SetVal(name, val) -> bool``.  The starting
numbers are test data, not facts about any instrument: each is marked ``# placeholder``.  Nothing here talks to a
device.
"""


class FakeInstrument:
    def __init__(self, **_options):
        # Placeholder starting values; the real controls are supplied by the value manager of a deployed
        # instrument and this fake has no knowledge of any physical range.
        self._values = {
            "EHT": 200000.0,        # placeholder: accelerating voltage in volts
            "C10": 0.0,             # placeholder: defocus in meters
            "ZLPoffset": 0.0,       # placeholder: energy offset in electron volts
            "BeamCurrent": 1.0e-11,  # placeholder: beam current in amperes
        }

    def GetVal(self, s, default_value=None):
        if s in self._values:
            return self._values[s]
        if default_value is None:
            raise KeyError(f"No element named '{s}' exists! Cannot get value.")
        return default_value

    def SetVal(self, s, val):
        self._values[s] = float(val)
        return True
