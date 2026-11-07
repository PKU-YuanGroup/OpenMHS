"""OpenMHS driver for gh.7jameslondon/magscope: the focus-axis adapter of a python-microscope stage.

A direct Driver over ``magscope.python_microscope:PythonMicroscopeFocusMotor``, the upstream adapter that exposes a
python-microscope stage (or one of its axes) as a MagScope absolute-Z focus motor.  The adapter divides a commanded Z by
``position_scale`` before calling the axis ``move_to`` and multiplies the axis position by the same scale on the way
back (magscope/python_microscope.py:184-192), so the driver publishes Z in micrometres and requests the native value in
nanometres.  The operator's ``position_scale`` therefore has to make the adapter report MagScope Z units as
nanometres: the connection guide's example uses 1000.0 when the microscope axis reports micrometres
(docs/source/connect_hardware.rst:75).

* reads: the reported Z position, the last target this driver commanded, the moving flag and the axis' own travel
  limits;
* one write: the absolute Z target, through the adapter's ``move_absolute``;
* one catalogue action: ``cap.imaging.focus.v1`` with the upstream's ``manual`` and ``none`` methods (the adapter
  has no autofocus search, so the upstream ``autofocus`` method is not offered);
* the native stop is the adapter's only motion command: command the axis to the position it reports now.  The
  upstream adapter has no dedicated stop or hold call (magscope/hardware.py:201-215).

No text file of the clone states a Z travel range for a stage; the adapter reads the bounds of the connected axis at
run time (magscope/python_microscope.py:214-220), which depend on the stage.  The Z target is therefore
``Limit.operator_required``: every write is refused ``MHS.SAFETY.LIMITS_UNSET`` until the site supplies the range.

This package is model-authored and unreviewed.  It is checked on the fake backend only; the hardware path
(``native.py``) was never run.
"""

from mhs.driver import Driver, DriverFailed, Fact, Field, Limit, action, estop, read, write

_LIMIT_REASON = (
    "no text file of the clone states a Z travel range for a python-microscope stage: the adapter reads the bounds "
    "of the connected axis at run time (magscope/python_microscope.py:214-220), so the site supplies the range of "
    "its stage"
)


class MagscopeFocus(Driver):
    device_id = "magscope-focus"
    device_kind = "instrument.microscope"
    mode = "hardware"
    risk = "R1"
    native = "magscope.python_microscope:PythonMicroscopeFocusMotor"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeMagscopeFocusMotor"}
    vendor, model = "7jameslondon", "python-microscope focus stage (MagScope adapter)"
    display_name = "MagScope focus motor (magscope.PythonMicroscopeFocusMotor)"
    tags = ["microscope", "focus", "z-stage", "python-microscope", "magscope"]
    facts = [
        Fact("PythonMicroscopeFocusMotor is a FocusMotorBase adapter for a python-microscope stage or stage axis",
             source="upstream_code", ref="magscope/python_microscope.py:142-143"),
        Fact("The adapter requires exactly one of device, device_factory or device_uri",
             source="upstream_code", ref="magscope/python_microscope.py:33-37"),
        Fact("connect() enables the device, resolves the configured axis and marks the motor connected",
             source="upstream_code", ref="magscope/python_microscope.py:170-176"),
        Fact("move_absolute() divides Z by position_scale and calls the axis' move_to() in device units",
             source="upstream_code", ref="magscope/python_microscope.py:184-188"),
        Fact("get_current_z() reads axis.position and multiplies it by position_scale",
             source="upstream_code", ref="magscope/python_microscope.py:190-192"),
        Fact("get_position_limits() reads the axis' limits.lower and limits.upper and converts both with "
             "position_scale", source="upstream_code", ref="magscope/python_microscope.py:214-220"),
        Fact("get_is_moving() reads the axis' moving/is_moving attribute or get_is_moving() method, and otherwise "
             "compares the current Z with the last commanded target using at_target_tolerance",
             source="upstream_code", ref="magscope/python_microscope.py:194-212"),
        Fact("FocusMotorBase defines move_absolute, get_current_z, get_is_moving and get_position_limits as its "
             "abstract device methods and has no stop primitive",
             source="upstream_code", ref="magscope/hardware.py:201-215"),
        Fact("position_scale converts python-microscope stage units into the absolute Z units MagScope uses; for "
             "example 1000.0 converts an axis that reports micrometres into nanometres",
             source="vendor_doc", ref="docs/source/connect_hardware.rst:75"),
        Fact("MagScope Z-Lock corrections are in nanometres", source="vendor_doc",
             ref="docs/source/user_guide.rst:787"),
    ]
    safe_state = ("focus axis commanded to the position it reports now (the adapter has no dedicated stop call; "
                  "move_absolute is its only motion primitive)")

    #: Last absolute Z target this driver commanded, in the native nanometre unit.  The adapter's own
    #: ``get_target_z()`` is only maintained by its MagScope IPC handler, which needs the MagScope shared buffer, so
    #: a standalone adapter is asked to move and its reported position is read back instead.
    _target_z_nm: float | None = None

    # -- reads ------------------------------------------------------------------------------------------------
    @read("current_z", unit="um", native_unit="nm",
          description="Absolute Z position the focus axis reports now")
    def current_z(self):
        return self.native.get_current_z()

    @read("target_z", unit="um", native_unit="nm",
          description="Last absolute Z target this driver commanded; before the first command, the reported position")
    def target_z(self):
        if self._target_z_nm is None:
            return self.native.get_current_z()
        return self._target_z_nm

    @read("is_moving", type="boolean", description="True while the focus axis reports that it is moving")
    def is_moving(self):
        return bool(self.native.get_is_moving())

    @read("lower_limit", unit="um", native_unit="nm",
          description="Lower Z travel limit the connected stage axis reports")
    def lower_limit(self):
        return self.native.get_position_limits()[0]

    @read("upper_limit", unit="um", native_unit="nm",
          description="Upper Z travel limit the connected stage axis reports")
    def upper_limit(self):
        return self.native.get_position_limits()[1]

    # -- the write --------------------------------------------------------------------------------------------
    @write("target_z", unit="um", native_unit="nm",
           description="Absolute Z target for the focus axis, handed to the adapter's move_absolute",
           limit=Limit.operator_required(_LIMIT_REASON))
    def set_target_z(self, value):
        self.native.move_absolute(float(value))
        self._target_z_nm = float(value)

    # -- the catalogue action --------------------------------------------------------------------------------
    @action(cap="cap.imaging.focus.v1",
            description="Move the focus axis to an absolute Z target (method 'manual') or report its current Z "
                        "(method 'none'); autofocus is not implemented by the adapter",
            input={
                "method": Field("string", enum=["manual", "none"],
                                description="Motion to run: 'manual' moves to target_z, 'none' only reads the "
                                            "current Z"),
                "target_z": Field("number", unit="um", native_unit="nm",
                                  description="Absolute Z target, required by method 'manual'",
                                  limit=Limit.operator_required(_LIMIT_REASON)),
            })
    def focus(self, method, target_z=None):
        if method == "manual":
            if target_z is None:
                raise DriverFailed("MHS.DEVICE.PRECONDITION_UNMET",
                                   "method 'manual' needs a target_z")
            self.native.move_absolute(float(target_z))
            self._target_z_nm = float(target_z)
        elif method != "none":
            raise DriverFailed("MHS.DEVICE.PRECONDITION_UNMET",
                               f"the focus adapter has no method {method!r} (manual or none)")
        z_nm = float(self.native.get_current_z())
        return {"focused": not bool(self.native.get_is_moving()), "z_um": z_nm / 1000.0}

    # -- safety -----------------------------------------------------------------------------------------------
    @estop(native="move_absolute")
    def stop(self):
        """Command the axis to the position it reports now: the adapter has no dedicated stop call."""
        current = float(self.native.get_current_z())
        self.native.move_absolute(current)
        self._target_z_nm = current
