"""Fake backend of the Kinesis piezo driver: an in-memory stand-in for piezo:PiezoController.

Gate G7: every public method of FakeKinesisPiezo exists on piezo:PiezoController (piezo.py:159-340).  The reader
object is the same shape the upstream class assigns in ``self.reader = StrainReader(...)`` (piezo.py:224-225):
``get_pos``, ``set_zero``, ``is_zeroing`` and ``get_units`` occur in piezo.py:134-153.  The driver reaches the reader
through ``controller.reader``, exactly as the upstream methods do.

Every value here is test data, not a fact about a device (each starting value is marked ``# placeholder``).  The fake
starts in closed loop with a placeholder calibration so the calibrated move can be exercised before calibrate_pos is
called; the hardware driver refuses that move until the real calibration exists.  The values never move by
themselves, so reading the state twice gives the same state.  Nothing here talks to a device.
"""

# placeholder: the fake maps percentage travel to strain gauge units at this fixed rate (10 units at 50 percent)
_READER_UNITS_PER_PERCENT = 0.2


class _FakeStrainReader:
    """The strain gauge reader object a real PiezoController owns (``controller.reader``)."""

    def __init__(self, controller):
        self._controller = controller
        self._reading = 10.0         # placeholder: fake starting reading
        self._zeroing = False        # placeholder: fake starts outside a zeroing operation

    def get_pos(self):
        return self._reading

    def set_zero(self):
        self._zeroing = True
        self._reading = 0.0          # placeholder: the zero point

    def is_zeroing(self):
        return self._zeroing

    def get_units(self):
        return "\u03bcm"


class FakeKinesisPiezo:
    def __init__(self, **_options):
        self.reader = _FakeStrainReader(self)
        self.a = 5.0                 # placeholder: calibration slope that maps 10 units to 50 percent
        self.b = 0.0                 # placeholder: calibration offset
        self._closed_loop = True     # placeholder: the fake starts in closed loop
        self._percentage = 50.0      # placeholder: fake starting percentage travel
        self._voltage = 0.0          # placeholder: fake starting output voltage

    # -- state ----------------------------------------------------------------------------------------------------
    def get_units(self):
        return "%" if self._closed_loop else "V"

    def get_value(self):
        return self._percentage if self._closed_loop else self._voltage

    def is_closed_loop(self):
        return self._closed_loop

    # -- writes ---------------------------------------------------------------------------------------------------
    def set_value(self, Value):
        if self._closed_loop:
            self._percentage = float(Value)
            self.reader._reading = self._percentage * _READER_UNITS_PER_PERCENT
        else:
            self._voltage = float(Value)

    def set_closed_loop(self):
        self._closed_loop = True
        self.reader._reading = self._percentage * _READER_UNITS_PER_PERCENT

    def set_open_loop(self):
        self._closed_loop = False

    # -- native motion --------------------------------------------------------------------------------------------
    def moveup(self):
        if self._closed_loop:
            self._percentage += 1.0
            self.reader._reading = self._percentage * _READER_UNITS_PER_PERCENT
        else:
            self._voltage += 1.0

    def movedown(self):
        if self._closed_loop:
            self._percentage -= 1.0
            self.reader._reading = self._percentage * _READER_UNITS_PER_PERCENT
        else:
            self._voltage -= 1.0

    def move_to_home(self):
        if self._closed_loop:
            self._percentage = 0.0
            self.reader._reading = 0.0
        else:
            self._voltage = 0.0

    def calibrate_pos(self):
        if not self._closed_loop:
            return
        y1, y2 = 10.0, 70.0
        self._percentage = y1
        self.reader._reading = self._percentage * _READER_UNITS_PER_PERCENT
        x1 = self.reader.get_pos()
        self._percentage = y2
        self.reader._reading = self._percentage * _READER_UNITS_PER_PERCENT
        x2 = self.reader.get_pos()
        self.a = (y2 - y1) / (x2 - x1)
        self.b = -self.a * x1 + y1
        y = self.a * 1.0 + self.b
        self._percentage = y
        self.reader._reading = self._percentage * _READER_UNITS_PER_PERCENT

    def move_to_pos(self, value):
        self._percentage = self.a * float(value) + self.b
        self.reader._reading = self._percentage * _READER_UNITS_PER_PERCENT

    def move_pos_up(self):
        if self.reader.get_pos() < 19:
            self.move_to_pos(self.reader.get_pos() + 1)

    def move_pos_down(self):
        if self.reader.get_pos() > 1:
            self.move_to_pos(self.reader.get_pos() - 1)

    def move_pos_to_home(self):
        self.move_to_pos(0)
