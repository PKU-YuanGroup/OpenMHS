"""OpenMHS driver for gh.pymodaq/pymodaq_plugins_physik_instrumente: PI GCS2 stage axes.

A direct Driver over ``pymodaq_plugins_physik_instrumente.hardware.pi_wrapper:PIWrapper`` (pi_wrapper.py:29), the
wrapper the PyMoDAQ plugin uses around a pipython ``GCSDevice`` (pi_wrapper.py:7, 29-48).  The controller is
multi-axis: ``axis_names`` is the controller's ``axes`` list (pi_wrapper.py:84-87) and every motion method takes the
axis name the controller reports.

* reads: the controller identity (qIDN, pi_wrapper.py:80-82), the axis names, the axis units the controller reports
  (pi_wrapper.py:89-115), the position of every axis (qPOS, pi_wrapper.py:282-289), the referenced state (qFRF,
  pi_wrapper.py:261-276) and the closed-loop state (qSVO, pi_wrapper.py:147-149);
* ``x-cap.pymodaq.pi_move_absolute.v1`` and ``x-cap.pymodaq.pi_move_relative.v1``: the native ``move_absolute``
  (MOV, pi_wrapper.py:291-299) and ``move_relative`` (MVR, pi_wrapper.py:301-310);
* ``x-cap.pymodaq.pi_home_axis.v1``: the native ``move_home`` (set_referencing, then GOH or FRF, pi_wrapper.py:312-329);
* ``x-cap.pymodaq.pi_stop_motion.v1``: the native ``stop`` (StopAll, pi_wrapper.py:278-280), also the safe-state
  action; it takes no input because StopAll takes no profile and reports no position (the catalogue stop class
  carries an optional deceleration and a stopped position that the wrapper cannot express);
* the native stop is the e-stop.

The clone states no travel range for the axes: ``get_axis_limits`` asks the controller for qTMN/qTMX at run time and
the clone itself carries no number (pi_wrapper.py:182-202), and the wrapper can drive any GCS2 stage (README.rst:30-31).
Every position and delta input is therefore ``Limit.operator_required`` until the site supplies the range of its
stages (``site-limits.example.json`` shows the overlay).

Positions and moves are in the controller's own axis units, which ``get_axis_units`` reports; the MHS fields publish
them as the dimensionless UCUM unit ``1`` and no conversion is applied, because a PI controller may have linear (mm,
um) and rotation (deg) axes in the same chassis.

Every Fact cites a line of the clone at the pinned commit (6fb8d954c432eac431e87c511a70e82c7b4df5f8).  This package is
model-authored and unreviewed: it is checked on the fake backend only and nothing here ran on hardware.
"""

from mhs.driver import Driver, DriverFailed, Fact, Field, Limit, action, estop, read

SOURCE = "src/pymodaq_plugins_physik_instrumente/hardware/pi_wrapper.py"
PLUGIN = "src/pymodaq_plugins_physik_instrumente/daq_move_plugins/daq_move_PI.py"

_MOVE_RANGE_REASON = (
    "no text file of the clone states the travel range of the axes: the wrapper reads the controller's own "
    "qTMN/qTMX limits at run time (pi_wrapper.py:182-202) and the axes may be any GCS2 stage (README.rst:30-31), "
    "so the site states the allowed range of its stages"
)


class PIController(Driver):
    device_id = "pi-gcs2"
    device_kind = "motion.axis"
    mode = "hardware"
    risk = "R1"
    native = "pymodaq_plugins_physik_instrumente.hardware.pi_wrapper:PIWrapper"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakePIWrapper"}
    vendor = "Physik Instrumente (PI)"
    model = "GCS2 controller with PI stages"
    display_name = "PI GCS2 stage controller (PyMoDAQ PIWrapper)"
    tags = ["motion", "stage", "actuator", "piezo", "pi", "gcs2"]
    facts = [
        Fact("PIWrapper wraps a pipython GCSDevice and its docstring lists the GCS2 controller families it supports",
             source="upstream_code", ref=f"{SOURCE}:29-48"),
        Fact("PIWrapper.identify() returns the controller identity from GCSDevice.qIDN()", source="upstream_code",
             ref=f"{SOURCE}:80-82"),
        Fact("PIWrapper.axis_names returns the controller's axes from GCSDevice.axes", source="upstream_code",
             ref=f"{SOURCE}:84-87"),
        Fact("PIWrapper.get_axis_units() queries parameter 0x07000601 for every axis, returns the reported unit and "
             "falls back to the default 'mm' when the controller rejects qSPA", source="upstream_code",
             ref=f"{SOURCE}:89-115"),
        Fact("PIWrapper.get_servo() reads the closed-loop state of an axis with qSVO", source="upstream_code",
             ref=f"{SOURCE}:147-149"),
        Fact("PIWrapper.set_referencing() sends RON and FRF only for an axis that is already referenced",
             source="upstream_code", ref=f"{SOURCE}:164-180"),
        Fact("PIWrapper.get_axis_limits() reads qTMN and qTMX for the axis and returns NaN when the command is not "
             "available", source="upstream_code", ref=f"{SOURCE}:182-202"),
        Fact("PIWrapper.connect_device() connects over USB, TCP/IP or RS232 and opens an RS232 line at 19200 baud",
             source="upstream_code", ref=f"{SOURCE}:233-244"),
        Fact("PIWrapper.is_referenced() reads the referenced state with qFRF when the device has it",
             source="upstream_code", ref=f"{SOURCE}:261-276"),
        Fact("PIWrapper.stop() sends StopAll to the controller", source="upstream_code", ref=f"{SOURCE}:278-280"),
        Fact("PIWrapper.get_axis_position() reads the position of the axis with qPOS", source="upstream_code",
             ref=f"{SOURCE}:282-289"),
        Fact("PIWrapper.move_absolute() sends MOV with the axis name and the position", source="upstream_code",
             ref=f"{SOURCE}:291-299"),
        Fact("PIWrapper.move_relative() sends MVR with the axis name and the position when the controller has MVR",
             source="upstream_code", ref=f"{SOURCE}:301-310"),
        Fact("PIWrapper.move_home() calls set_referencing(), then GOH or FRF, and falls back to an absolute move to 0",
             source="upstream_code", ref=f"{SOURCE}:312-329"),
        Fact("The DAQ_Move_PI plugin declares um as its default controller unit", source="upstream_code",
             ref=f"{PLUGIN}:42"),
        Fact("The DAQ_Move_PI plugin reads axis_names and get_axis_units from the wrapper at initialization",
             source="upstream_code", ref=f"{PLUGIN}:109-110"),
        Fact("The DAQ_Move_PI plugin stops the controller with controller.stop() in stop_motion()", source="upstream_code",
             ref=f"{PLUGIN}:136-141"),
        Fact("The README states that the PI actuator plugin covers all stages compatible with the GCS2 library and "
             "was tested on E-816, C-863, C-663 and E-545", source="vendor_doc", ref="README.rst:30-31"),
    ]
    safe_state = "all axes stopped (the controller's StopAll command)"

    # -- helpers ---------------------------------------------------------------------------------------------------
    def _axes(self):
        return [str(axis) for axis in self.native.axis_names]

    def _check_axis(self, axis):
        axes = self._axes()
        if axis not in axes:
            raise DriverFailed("MHS.DEVICE.PRECONDITION_UNMET",
                              f"axis {axis!r} is not one of the controller's axes {axes}")
        return axis

    # -- reads -----------------------------------------------------------------------------------------------------
    @read("identity", type="string", description="Controller identity string from the native identify() (qIDN)")
    def identity(self):
        return str(self.native.identify())

    @read("axis_names", type="array", items=Field("string"),
          description="Axis names the controller reports, in the order the native array reports them")
    def axis_names(self):
        return self._axes()

    @read("axis_units", type="array", items=Field("string"),
          description="Unit string the controller reports for each axis, in axis order")
    def axis_units(self):
        return [str(unit) for unit in self.native.get_axis_units()]

    @read("positions", type="array", unit="1", items=Field("number", unit="1"),
          description="Position of every axis in the controller's own units (the axis_units read), as qPOS reports it")
    def positions(self):
        return [float(self.native.get_axis_position(axis)) for axis in self._axes()]

    @read("referenced", type="array", items=Field("boolean"),
          description="Referenced state of every axis in axis order, as the native is_referenced() reports it")
    def referenced(self):
        return [bool(self.native.is_referenced(axis)) for axis in self._axes()]

    @read("servo_enabled", type="array", items=Field("boolean"),
          description="Closed-loop state of every axis in axis order, as the native get_servo() reports it")
    def servo_enabled(self):
        return [bool(self.native.get_servo(axis)) for axis in self._axes()]

    # -- moves -----------------------------------------------------------------------------------------------------
    @action(name="x-cap.pymodaq.pi_move_absolute.v1",
            description="Move one axis to an absolute position with the native move_absolute() and report the "
                        "position the controller reads back",
            input={"axis": Field("string", description="Axis name the controller reports (one of axis_names)"),
                   "position": Field("number", unit="1",
                                     description="Absolute position in the controller's axis unit",
                                     limit=Limit.operator_required(_MOVE_RANGE_REASON))},
            output={"axis": Field("string", description="Axis the native move_absolute() was given"),
                    "position": Field("number", unit="1",
                                      description="Position the controller reports after the move")})
    def move_absolute(self, axis, position):
        self._check_axis(axis)
        self.native.move_absolute(axis, position)
        return {"axis": axis, "position": float(self.native.get_axis_position(axis))}

    @action(name="x-cap.pymodaq.pi_move_relative.v1",
            description="Move one axis by a relative step with the native move_relative() and report the position the "
                        "controller reads back",
            input={"axis": Field("string", description="Axis name the controller reports (one of axis_names)"),
                   "delta": Field("number", unit="1",
                                  description="Relative step in the controller's axis unit",
                                  limit=Limit.operator_required(_MOVE_RANGE_REASON))},
            output={"axis": Field("string", description="Axis the native move_relative() was given"),
                    "position": Field("number", unit="1",
                                      description="Position the controller reports after the step")})
    def move_relative(self, axis, delta):
        self._check_axis(axis)
        self.native.move_relative(axis, delta)
        return {"axis": axis, "position": float(self.native.get_axis_position(axis))}

    @action(name="x-cap.pymodaq.pi_home_axis.v1",
            description="Home one axis with the native move_home() and report whether the controller then reports it "
                        "as referenced",
            input={"axis": Field("string", description="Axis name the controller reports (one of axis_names)")},
            output={"axis": Field("string", description="Axis the native move_home() was given"),
                    "referenced": Field("boolean",
                                        description="Referenced state the controller reports after the homing move")})
    def home_axis(self, axis):
        self._check_axis(axis)
        self.native.move_home(axis)
        return {"axis": axis, "referenced": bool(self.native.is_referenced(axis))}

    # -- stop ------------------------------------------------------------------------------------------------------
    @action(name="x-cap.pymodaq.pi_stop_motion.v1", safe_state=True,
            description="Stop all motion with the native stop() (the controller's StopAll command). It takes no "
                        "input because the native stop takes no profile or position",
            output={"stopped": Field("boolean", description="True once the native stop() returned")})
    def stop_motion(self):
        self.native.stop()
        return {"stopped": True}

    # -- safety ----------------------------------------------------------------------------------------------------
    @estop
    def stop(self):
        """The native stop: the runtime latches first, then sends StopAll."""
        self.native.stop()

    def teardown(self):
        self.native.close()
