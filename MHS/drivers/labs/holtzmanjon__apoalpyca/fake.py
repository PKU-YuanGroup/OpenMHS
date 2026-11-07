"""Analytic Alpaca fake of the APO dome server for the TagDriver acceptance gate.

It stores the five declared properties and answers the five declared methods
with the state transitions the server causes: AbortSlew clears the slewing
flag; SlewToAzimuth, Park and FindHome set it as the worker thread's rotate()
does (here at once, unless ``start_delayed`` models a worker that has not yet
reached rotate()); Park does nothing when already at park and FindHome does
nothing when already home (``device/APOAshDome.py:148-153``, ``:309-314``); a
slew target within ``DOME_TOLERANCE`` of the current azimuth starts no rotation
(``:41``, ``:387-388``); SetPark stores the current azimuth as the park
position. Every number below is placeholder test data, not a device fact. The
fake models no motion, encoder, weather check, shutter, louver subprocess,
watchdog, worker thread timing or Alpaca transport error; it never claims that
a slew reached a position.
"""

from mhs.bridge.tag_fake import RecordingTagTransport

_DOME_TOLERANCE = 3  # device/APOAshDome.py:41


def _diff(azimuth, current):
    """Shortest signed angle, as the upstream diff() computes it (device/APOAshDome.py:450-456)."""
    delta = azimuth - current
    if delta > 180:
        delta -= 360
    elif delta < -180:
        delta += 360
    return delta


class FakeApoDome(RecordingTagTransport):
    def __init__(self, **_options):
        super().__init__("alpaca")
        self.properties.update({
            "azimuth": 200.0,        # placeholder: arbitrary encoder angle
            "shutterstatus": 1,      # placeholder: ASCOM closed
            "slewing": False,        # placeholder: at rest
            "athome": False,         # placeholder: not on the home switch
            "atpark": False,         # placeholder: park position differs
        })
        self.park_position = 60.0    # placeholder: stored park angle
        #: Test switch: the worker thread has not reached rotate() yet, so the flag stays false.
        self.start_delayed = False

    def _start_rotation(self):
        if not self.start_delayed:
            self.properties["slewing"] = True

    def on_invoke(self, request, args):
        member = request["member"]
        if member == "abortslew":
            self.properties["slewing"] = False
            return 0
        if member == "slewtoazimuth":
            target = args.get("Azimuth")
            if type(target) is not int:
                return 0x401                            # Alpaca InvalidValue
            if abs(_diff(target, self.properties["azimuth"])) >= _DOME_TOLERANCE:
                self._start_rotation()
                self.properties["atpark"] = False
            return 0
        if member == "park":
            if not self.properties["atpark"]:
                self._start_rotation()
            return 0
        if member == "findhome":
            if not self.properties["athome"]:
                self._start_rotation()
            return 0
        if member == "setpark":
            self.park_position = float(self.properties["azimuth"])
            self.properties["atpark"] = True
            return 0
        return 0x40C                                    # Alpaca ActionNotImplemented
