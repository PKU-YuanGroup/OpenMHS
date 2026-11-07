"""Fake backend of the HP 89400 driver: an in-memory stand-in for HP894xx.HP89400Device:HP89400Device.

Gate G7: every public method defined here exists on the upstream class (python/HP894xx/HP89400Device.py),
and the driver touches only those methods.  The replies use the upstream shape: a query reply is the text
of the GPIB answer, and ``read_data`` returns a list of floats (python/HP894xx/HP89400Device.py:198-211).
Every numeric value or reply below is placeholder test data, marked ``# placeholder``: the real centre,
span, point count, average count and trace are settings of the analyzer and are not stated by the clone.
Nothing here talks to a device.
"""


class FakeHP89400:
    def __init__(self, **_options):
        self._center = "+2.50000000000000E+006"     # placeholder: 2.5 MHz centre
        self._span = "+5.00000000000000E+006"       # placeholder: 5 MHz span
        self._x_units = "HZ"                        # placeholder: the README sample's X unit
        self._y_units = "VRMS/RTHZ"                 # placeholder: the README sample's Y unit
        self._points = 8                            # placeholder: a small trace
        self._averages = 16                         # placeholder: the fake's average count
        self._operating_condition = 0               # placeholder: no operating-condition bit set
        self._error = '0,"No error"'                # placeholder: an empty error queue
        self._values = [                         # placeholder: one 8-point trace
            5.42512054835242e-07,
            5.42191457952867e-07,
            5.41927079211746e-07,
            5.41535314368957e-07,
            5.40725523023866e-07,
            5.39124130227719e-07,
            5.36303559783846e-07,
            5.31816908733163e-07,
        ]
        self._autorange = False
        self._aborted = False

    def GetXCenter(self):
        return self._center

    def GetXSpan(self):
        return self._span

    def GetXUnits(self):
        return self._x_units

    def GetYUnits(self):
        return self._y_units

    def GetDataLength(self):
        return self._points

    def GetReadDataPoints(self):
        return self._averages

    def get_operating_condition(self):
        return self._operating_condition

    def read_error_code(self):
        return 0                                    # placeholder: the leading code of the error entry

    def read_errors(self):
        return self._error

    def StartDataRead(self):
        self._aborted = False

    def read_data(self):
        return list(self._values)

    def abort(self):
        self._aborted = True

    def enable_autorange(self, setting):
        self._autorange = bool(setting)
