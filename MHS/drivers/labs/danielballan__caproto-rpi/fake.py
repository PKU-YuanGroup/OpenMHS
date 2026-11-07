"""Deterministic Channel Access fake for the caproto-rpi hat IOC's state PV.

The fake answers only the declared PV suffix.  It applies the upstream
``write_state`` truthiness rule to its own ``state`` read-back: any truthy
value reads back as 1 and any falsy value as 0 (``iocs/hat.py:25-32``).

The initial value is a placeholder, not a device fact.  The fake models no
GPIO pin, LED or failure mode of a real board, and it is an analytic
stand-in, not a recording of a deployed IOC.
"""

from mhs.bridge.tag_fake import RecordingTagTransport


class FakeCaprotoRpi(RecordingTagTransport):
    def __init__(self, **_options):
        super().__init__("epics-ca")
        self.pvs.update({
            "state": 0,          # placeholder: all configured pins LOW
        })

    def on_write(self, request, raw):
        if request["pv"] == "state":
            # write_state maps any truthy value to GPIO.HIGH and any falsy value to GPIO.LOW.
            self.pvs["state"] = 1 if raw else 0
