"""Fake backend of the zaber_x_adr130 driver: an in-memory stand-in for zaber_X_ADR130:Controller.

Gate G7: every public method defined here (get_position_mm, move_mm, get_maxspeed, set_maxspeed, close), and the one
private name the driver reaches (_stop_x and _stop_y), is a method of the upstream Controller.  The clone has no
simulator or mock, so this is an in-memory fake at the level of the upstream methods; it opens no serial port and
moves nothing.  The method shapes follow the upstream (move_mm(x_mm, y_mm, relative=True, block=True), lines 246-258;
set_maxspeed(x_mmps=None, y_mmps=None), lines 271-283; get_maxspeed, lines 260-269).  Every number below is test data
(# placeholder), not a fact about the stage.
"""


class FakeZaberXAdr130:
    def __init__(self, **_options):
        self._x_mm = 10.0           # placeholder: test start position
        self._y_mm = 20.0           # placeholder: test start position
        self._x_mmps = 50.0         # placeholder: test start speed
        self._y_mmps = 25.0         # placeholder: test start speed
        self.stop_calls = 0         # placeholder: no stop was sent yet
        self.move_calls = 0         # placeholder: no move was sent yet

    def get_position_mm(self):
        return self._x_mm, self._y_mm

    def move_mm(self, x_mm, y_mm, relative=True, block=True):
        if relative:
            x_mm = self._x_mm + float(x_mm)
            y_mm = self._y_mm + float(y_mm)
        self._x_mm = float(x_mm)
        self._y_mm = float(y_mm)
        self.move_calls += 1

    def get_maxspeed(self):
        return self._x_mmps, self._y_mmps

    def set_maxspeed(self, x_mmps=None, y_mmps=None):
        if x_mmps is not None:
            self._x_mmps = float(x_mmps)
        if y_mmps is not None:
            self._y_mmps = float(y_mmps)

    def _stop_x(self):
        self.stop_calls += 1

    def _stop_y(self):
        self.stop_calls += 1

    def close(self):
        pass
