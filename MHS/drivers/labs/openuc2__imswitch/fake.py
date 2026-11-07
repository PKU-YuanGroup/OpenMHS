"""Fake backend of the UC2 ESP32 stage driver: an in-memory stand-in for the upstream positioner manager.

Gate G7: every public member defined here exists on
``imswitch.imcontrol.model.managers.positioners.ESP32StageManager.ESP32StageManager``: ``move``
(``ESP32StageManager.py:432``), ``getPosition`` (line 605), ``stopAll`` (line 647), ``closeEvent`` (line 602) and the
``position`` property its ``PositionerManager`` base defines (``PositionerManager.py:59-63``).

The fake keeps the upstream semantics the driver relies on (model review):

* ``getPosition()`` answers a device query with a new dict (A, X, Y, Z in µm, user frame), as the upstream builds a new
  ``posDict`` from ``_motor.get_position()``; when the query fails it returns the cached ``_position`` object itself,
  as the upstream does after logging the exception (``ESP32StageManager.py:605-617``);
* ``position`` returns that cached ``_position`` (``PositionerManager.py:59-63``);
* an XYZ ``move`` writes the commanded target into the cache after the motor call (``ESP32StageManager.py:542-544``);
  the fake's device position arrives at once.

It does not model motor time, acceleration, step loss, backlash, the uc2rest client, the ESP32 serial protocol or the
firmware, nor the single-axis branches' speed and soft-limit checks, which the driver never uses.  The stage starts
at placeholder positions; no value here is a fact about a device and every number is marked ``# placeholder``.
Nothing here talks to a device or opens a port.

Two switches give the negative paths of the tests (placeholders, not upstream behaviour the clone shows):
``keeps_moving=True`` is a stage that does not stop (its position changes on every query, also after ``stopAll``),
``query_fails=True`` is a device position query that raises, so ``getPosition()`` returns the cache.
"""


class FakeESP32StageManager:
    def __init__(self, *, keeps_moving=False, query_fails=False, **_options):
        self._position = {"A": 0.0, "X": 0.0, "Y": 0.0, "Z": 0.0}   # placeholder start positions (the cache)
        self._device = dict(self._position)   # placeholder device positions, as a query reports them
        self._keeps_moving = bool(keeps_moving)
        self._query_fails = bool(query_fails)
        self._stop_calls = 0

    @property
    def position(self):
        """The cached per-axis position, as the PositionerManager property returns it."""
        return self._position

    def move(self, value=0, axis="X", is_absolute=False, is_blocking=True, acceleration=None, speed=None,
             isEnable=None, timeout=100, is_reduced=True):
        """Move the device at once and update the cache as the upstream does after the motor call."""
        if axis == "XYZ":
            for name, item in zip(("X", "Y", "Z"), value):
                self._device[name] = float(item) if is_absolute else self._device[name] + float(item)
                self._position[name] = float(item) if is_absolute else self._position[name] + float(item)
        elif axis in ("X", "Y", "Z", "A"):
            self._device[axis] = float(value) if is_absolute else self._device[axis] + float(value)
            self._position[axis] = float(value) if is_absolute else self._position[axis] + float(value)
        # any other axis is the upstream's "Wrong axis" branch, which changes nothing

    def getPosition(self):
        """A device query (a new dict), or the cached _position object itself when the query fails."""
        if self._query_fails:
            return self._position
        if self._keeps_moving:
            self._device["X"] += 25.0   # placeholder travel per query: the stage has not stopped
        return dict(self._device)

    def stopAll(self):
        """The native all-axis stop: the fake has no motion to halt (a keeps_moving stage ignores it)."""
        self._stop_calls += 1

    def closeEvent(self):
        """The upstream lifecycle hook is empty (ESP32StageManager.py:602-603)."""
