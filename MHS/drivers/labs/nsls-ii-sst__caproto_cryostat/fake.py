"""Deterministic EPICS-CA point store for the NSLS-II SST ADR TagDriver (read only).

The fake is a ``RecordingTagTransport`` with the ``epics-ca`` profile.  It
answers only the read PV suffixes the package declares.  Every number, string
and state below is test data, not a device fact or a limit; the fake models no
PID loop, heater, magnet cycle, ZeroMQ transport, 0.1 s scan or EPICS server
error.

Model review (2026-11-05): the package declares no writable point, so the
author's ``on_write`` read-back model and the seeds of ``TEMP_SP``, ``PAUSE``
and ``START_CYCLE`` were removed; any write request would be refused as an
undeclared point by the bridge before it reached this store.
"""

from mhs.bridge.tag_fake import RecordingTagTransport


class FakeADR(RecordingTagTransport):
    def __init__(self, **_options):
        super().__init__("epics-ca")
        self.pvs.update({
            "TEMP": 0.050,             # placeholder: a temperature in kelvin
            "TEMP_SP_RB": 0.050,       # placeholder: the setpoint read-back
            "TEMP_RMS_UK": 0.0,        # placeholder: a stability figure in microkelvin
            "ALT_TEMP": 0.050,         # placeholder: a second temperature channel
            "HEATER_OUT": 0.0,         # placeholder: a heater output
            "STATE": "Idle",           # placeholder: an ADR mode string
            "CYCLE_UID": "",           # placeholder: a cycle identifier
        })
        self.writes = 0

    def on_write(self, request, raw):
        # Never reached through the package: no point is writable.  Counted so a test can show nothing was written.
        self.writes += 1
