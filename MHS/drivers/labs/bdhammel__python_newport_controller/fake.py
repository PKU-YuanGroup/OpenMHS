"""Fake backend of the Picomotor driver: an in-memory stand-in for newport:Controller.

The upstream class has one public command method, ``command(newfocus_command)`` (newport.py:213-235), and this fake
defines exactly that one public method (gate G7).  It answers the NewFocus-style commands the driver sends:

* ``{axis}TP?`` -- the reported position of one channel, as the upstream parse_reply() would return it;
* ``{axis}PR{steps}`` -- a relative move by that many steps (README.md:108);
* ``ST`` -- stop all motor movement (README.md:107).

The starting positions and counters are test data, not facts about any device; the values never move by themselves,
so reading the state twice gives the same state.  Nothing here talks to a device.
"""

import re

_POSITION = re.compile(r"^([0-9])TP\?$")
_RELATIVE = re.compile(r"^([0-9])PR([+-]?[0-9]+)$")


class FakePythonNewportController:
    def __init__(self, **_options):
        # placeholder: canned channel positions for the fake only
        self._positions = {1: 1000, 2: -250, 3: 0, 4: 75}
        # placeholder: the fake starts with no stop command received
        self._stopped = False

    def command(self, newfocus_command):
        """Answer one NewFocus-style command, like newport.Controller.command()."""
        match = _POSITION.match(newfocus_command)
        if match:
            return str(self._positions[int(match.group(1))])

        match = _RELATIVE.match(newfocus_command)
        if match:
            axis, steps = int(match.group(1)), int(match.group(2))
            self._positions[axis] = self._positions.get(axis, 0) + steps     # placeholder start for other axes
            self._stopped = False
            return None

        if newfocus_command == "ST":
            self._stopped = True
            return None

        raise ValueError(f"the fake controller does not implement the command {newfocus_command!r}")
