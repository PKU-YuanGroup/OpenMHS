"""Fake backend of the K10CR1 driver: an in-memory stand-in for K10CR1.k10cr1:K10CR1.

Gate G7: every public method defined here is a method of the upstream class (K10CR1/k10cr1.py:6-189), and the driver
touches nothing else.  The fake keeps one angle in degrees and applies the moves to it, so a move is visible to the
next position read; the response frames are placeholders, not a recording of a device.

The values are test data, not facts: they are marked ``# placeholder`` and appear in no Fact or Limit.  The clone has
no simulator and no hardware was available.  Nothing here talks to a device.
"""

START_ANGLE = 0.0            # placeholder
HOME_RESPONSE = b"#000000"    # placeholder: the 6 bytes home() reads
JOG_RESPONSE = b"#00000000000000000000"    # placeholder: the 20 bytes jog() reads


class FakeK10CR1:
    def __init__(self, **_options):
        self._angle = START_ANGLE
        self._moves = []

    def getpos(self):
        return float("%.3f" % self._angle)

    def moveabs(self, x):
        self._moves.append(("abs", float(x)))
        self._angle = float(x)

    def moverel(self, x):
        self._moves.append(("rel", float(x)))
        self._angle = self._angle + float(x)

    def home(self):
        self._moves.append(("home", None))
        self._angle = START_ANGLE
        return HOME_RESPONSE

    def jog(self):
        self._moves.append(("jog", None))
        return JOG_RESPONSE
