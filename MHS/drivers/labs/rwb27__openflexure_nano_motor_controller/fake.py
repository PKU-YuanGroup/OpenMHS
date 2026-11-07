"""Fake backend of the OpenFlexure stage driver: an in-memory stand-in for OpenFlexureStage.

Gate G7: every public method and property defined on :class:`FakeOpenFlexureStage` exists on
``openflexure_stage.stage:OpenFlexureStage``.  The nested :class:`FakeEndstops` stands in for the optional
``stage.Endstops`` module (stage.py:379-424); its members are not the entry class's surface.  The driver only needs
``board``, ``position``, ``step_time``, ``ramp_time``, ``move_rel``, ``move_abs``, ``focus_rel``,
``release_motors``, ``endstops`` and ``close``, all of which the upstream class has.

The values below are test data, not device facts.  Every start value and canned reply is marked ``# placeholder``.
The fake does not model the stepper physics, the endstop switches or the firmware's serial timing; it only keeps the
position, the two timing settings and whether the coils were released.  Nothing here talks to a device.
"""


class FakeEndstops:
    """The optional Endstops module: status, maxima and homing, with no switches behind it."""

    def __init__(self, parent=None, model="min"):
        self._parent = parent
        self.model = model
        self.installed = model.split(" ")
        self.test_mode = False
        self._status = [0, 0, 0]            # placeholder: no endstop triggered
        self._maxima = [1000, 1000, 1000]   # placeholder: example maximum positions

    @property
    def available(self):
        return True

    @property
    def status(self):
        return list(self._status)

    @property
    def maxima(self):
        return list(self._maxima)

    def home(self, direction="min", axes=['x', 'y', 'z']):
        names = list(self._parent.axis_names)
        selected = [name for name in axes if name in names]
        if direction in ("min", "both"):
            for name in selected:
                self._parent._position[names.index(name)] = 0
        if direction in ("max", "both"):
            for name in selected:
                index = names.index(name)
                self._parent._position[index] = self._maxima[index]


class FakeOpenFlexureStage:
    """The stage object the driver sees: the same names as OpenFlexureStage, backed by plain attributes."""

    def __init__(self, **_options):
        self.axis_names = ("x", "y", "z")
        self.board = "OpenFlexure Motor Board v0.4"  # placeholder: canned version reply
        self.firmware_version = "0.4"                # placeholder: canned version reply
        self._position = [0, 0, 0]                   # placeholder: start position
        self._step_time = 1000                       # placeholder: start step delay in us
        self._ramp_time = 0                          # placeholder: start ramp time in us
        self._closed = False
        self.endstops = FakeEndstops(parent=self, model="min")

    @property
    def position(self):
        return list(self._position)

    @property
    def step_time(self):
        return self._step_time

    @property
    def ramp_time(self):
        return self._ramp_time

    def move_rel(self, displacement, axis=None, backlash=True):
        if axis is not None:
            assert axis in self.axis_names, "axis must be one of {}".format(self.axis_names)
            displacement = [int(displacement) if name == axis else 0 for name in self.axis_names]
        for index, delta in enumerate(displacement):
            self._position[index] += int(delta)

    def move_abs(self, final, **kwargs):
        self._position = [int(value) for value in final]

    def focus_rel(self, z):
        self.move_rel([0, 0, z])

    def release_motors(self):
        return None

    def close(self):
        self._closed = True
