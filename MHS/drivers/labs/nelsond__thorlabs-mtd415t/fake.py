"""Fake backend of the MTD415T driver: an in-memory stand-in for
``thorlabs_mtd415t.mtd415t_device:MTD415TDevice``.

The clone ships no device simulator (its ``tests/support/mock_serial.py`` is a pyserial-like transport stand-in, not
a device), so this package uses the card's preferred plain fake.  Gate G7: every public member here is a property or
method of the upstream class: ``temp``, ``temp_setpoint``, ``tec_current``, ``tec_voltage``,
``tec_current_limit``, ``errors``, ``idn`` and ``uid`` are properties of ``MTD415TDevice``
(thorlabs_mtd415t/mtd415t_device.py:126-333), and ``close`` and ``is_open`` belong to its ``SerialDevice`` base
(thorlabs_mtd415t/serial_device.py:50-54, 93-96).  The class never derives from MTD415TDevice and talks to nothing.

Every value below is placeholder test data, not a fact about a device and not a recording.  The controller reports
values derived from its serial replies (mtd415t_device.py:138-333); this object keeps fixed values so two reads
return the same state.  Nothing here opens a port.
"""


class FakeMTD415TDevice:
    def __init__(self, **_options):
        self._open = True
        self._temp = 24.5              # placeholder
        self._setpoint = 25.0          # placeholder
        self._tec_current = 0.35       # placeholder
        self._tec_voltage = 1.2        # placeholder
        self._tec_current_limit = 1.0  # placeholder
        self._errors = ()
        self._idn = "MTD415T fake"     # placeholder
        self._uid = "fake-uid"         # placeholder

    @property
    def temp(self):
        return self._temp

    @property
    def temp_setpoint(self):
        return self._setpoint

    @property
    def tec_current(self):
        return self._tec_current

    @property
    def tec_voltage(self):
        return self._tec_voltage

    @property
    def tec_current_limit(self):
        return self._tec_current_limit

    @property
    def errors(self):
        return self._errors

    @property
    def idn(self):
        return self._idn

    @property
    def uid(self):
        return self._uid

    @property
    def is_open(self):
        return self._open

    def close(self):
        self._open = False
