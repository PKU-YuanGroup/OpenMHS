"""OpenMHS driver for gh.rplab/wil_pycro_control_app: the ASI stage of the WIL Pycro control app.

The upstream repository is a PyQt acquisition application.  Its stage layer is
``WIL_Pycro_Control_App/hardware/stage.py``, a module of synchronous functions
over the Micro-Manager core (card entry ``pyfile:WIL_Pycro_Control_App/hardware/stage.py#*``).
The driver exposes the stage's three axes and the focus action:

* reads: X, Y and Z position in micrometres, from the core read-back functions;
* writes: X, Y and Z position through ``cap.device.configure.v1``.  No text file of the clone
  states the travel of the connected stage; the XY device and the focus device are selected in
  Micro-Manager, so every travel target is ``Limit.operator_required`` and is refused
  ``MHS.SAFETY.LIMITS_UNSET`` until the site supplies an envelope.  Each write moves one axis with
  the clone's per-axis function; none goes through ``move_stage``, whose Z/XY ordering the clone
  uses to keep capillaries from hitting the objective (stage.py:191-214);
* one action: ``cap.imaging.focus.v1``.  The clone has no autofocus routine, so only the
  ``manual`` move to a target Z and the ``none`` query are accepted by the binding;
* no stop (model review, 2026-11-05).  The clone has no stage halt.  Its only stop-like function,
  ``reset_stage``, sends the ASI RESET command, which its docstring says resets the console's
  flash memory, the origin and the joystick settings, and which it marks deprecated
  (stage.py:321-334); it goes through ``send_serial_command_to_stage``, which first waits for the
  XY stage to stop being busy (stage.py:51-57), so it cannot interrupt an XY move, and the
  runtime's background retry of a failed e-stop would send it again every few seconds.  The
  ``@estop`` therefore sends nothing and raises ``MHS.SAFETY.SAFE_STATE_UNREACHED``: the latch
  refuses new commands while a move already sent to the console continues.  The package is
  blocked (``NO_HARDWARE_FREE_PATH``) until the clone has a stop that it sends and confirms.

Loading the hardware backend imports the upstream ``hardware`` package, which reconfigures the
camera and programs the PLC trigger circuit at import (see ``native.py`` and the facts).

Every Fact cites a line of the clone at the pinned commit
(dc2f18836064c0e2391d96f0d72734e2a24764f8).  This package is model-authored and unreviewed:
it is checked on the fake backend only, and its hardware backend was never run.
"""

from mhs.driver import Driver, DriverFailed, Fact, Field, Limit, action, estop, read, write

#: The stage names come from Micro-Manager, so the connected model is deployment data.
_STAGE_SOURCE = ("WIL_Pycro_Control_App/hardware/stage.py:10-14 reads the XY stage and focus "
                 "device names from the Micro-Manager core")
_X_REASON = ("no text file of the clone states the X travel of the stage: " + _STAGE_SOURCE +
             ", so the connected stage may be configured differently; the site supplies the X envelope")
_Y_REASON = ("no text file of the clone states the Y travel of the stage: " + _STAGE_SOURCE +
             ", so the connected stage may be configured differently; the site supplies the Y envelope")
_Z_REASON = ("no text file of the clone states the Z travel of the focus device: " + _STAGE_SOURCE +
             ", so the connected stage may be configured differently; the site supplies the Z envelope")
_TARGET_Z_REASON = ("no text file of the clone states the Z travel of the focus device: " + _STAGE_SOURCE +
                    ", so the connected stage may be configured differently; the site supplies the focus envelope")


class WilPycroStage(Driver):
    device_id = "wil-pycro-stage"
    device_kind = "instrument.microscope"
    mode = "hardware"
    risk = "R1"
    native = "pyfile:WIL_Pycro_Control_App/hardware/stage.py#*"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeStage"}
    vendor, model = "WIL / rplab", "ASI stage of the WIL Pycro acquisition app"
    display_name = "WIL Pycro stage (hardware.stage)"
    tags = ["microscope", "stage", "focus", "asi", "micro-manager", "imaging"]
    facts = [
        Fact("The XY stage and focus device labels are read from the Micro-Manager core when stage.py is imported, "
             "beside the hard-coded ASI labels ASI-XYStage and XStage", source="upstream_code",
             ref="WIL_Pycro_Control_App/hardware/stage.py:10-14"),
        Fact("send_serial_command_to_stage sends a serial command to the ASI Tiger console only after "
             "core.wait_for_device(XY_STAGE_NAME) returns", source="upstream_code",
             ref="WIL_Pycro_Control_App/hardware/stage.py:51-57"),
        Fact("The X and Z stages are swapped, so the X-axis speed is set with the Z-axis SPEED command",
             source="upstream_code", ref="WIL_Pycro_Control_App/hardware/stage.py:68-71"),
        Fact("set_x_position takes x_pos in micrometres, waits for the XY stage, sets the default X speed and sends "
             "M Z=<int(x_pos)*TO_TENTHS>, the ASI MOVE command in tenths of microns", source="upstream_code",
             ref="WIL_Pycro_Control_App/hardware/stage.py:217-227"),
        Fact("set_y_position takes y_pos in micrometres, waits for the XY stage, sets the default Y speed and sends "
             "M Y=<int(y_pos)*TO_TENTHS>", source="upstream_code",
             ref="WIL_Pycro_Control_App/hardware/stage.py:230-239"),
        Fact("set_z_position takes z_pos in micrometres, waits for the Z stage, sets the default Z speed and passes "
             "z_pos unchanged to core.set_position(Z_STAGE_NAME, z_pos)", source="upstream_code",
             ref="WIL_Pycro_Control_App/hardware/stage.py:251-260"),
        Fact("get_x_position, get_y_position and get_z_position wait for their stage and return the core position "
             "truncated to int", source="upstream_code", ref="WIL_Pycro_Control_App/hardware/stage.py:263-293"),
        Fact("move_stage moves Z before XY when the current X is greater than the target X, and XY before Z "
             "otherwise; its comment says this keeps capillaries from hitting the objective and that the conditions "
             "should match the geometry of the holder", source="upstream_code",
             ref="WIL_Pycro_Control_App/hardware/stage.py:191-214"),
        Fact("wait_for_xy_stage and wait_for_z_stage block on the Micro-Manager core until the stage is not busy",
             source="upstream_code", ref="WIL_Pycro_Control_App/hardware/stage.py:39-49"),
        Fact("reset_stage sends RESET through send_serial_command_to_stage; its docstring says RESET resets the "
             "current flash memory of the Tiger console, most notably the origin (to its current position) and the "
             "joystick settings, and marks the function DEPRECATED", source="upstream_code",
             ref="WIL_Pycro_Control_App/hardware/stage.py:321-334"),
        Fact("general_exception_handle runs a hardware function up to two times, logging each exception; after the "
             "second failure it prints a message and raises GeneralHardwareException", source="upstream_code",
             ref="WIL_Pycro_Control_App/hardware/exceptions_handle.py:25-42"),
        Fact("Importing the hardware package sets the camera to its default mode and initializes the PLC state, "
             "suppressing GeneralHardwareException", source="upstream_code",
             ref="WIL_Pycro_Control_App/hardware/__init__.py:5-11"),
        Fact("default_mode stops sequence acquisition, turns live mode off and sets the camera trigger mode, acquire "
             "mode and exposure", source="upstream_code", ref="WIL_Pycro_Control_App/hardware/camera.py:55-74"),
        Fact("init_plc_state programs the PLC circuit used in z-stack acquisition and lsrm, whose pulse is sent to "
             "the camera as an external trigger", source="upstream_code",
             ref="WIL_Pycro_Control_App/hardware/plc.py:55-97"),
        Fact("utils.pycro constructs the pycromanager Studio and Core objects when it is imported",
             source="upstream_code", ref="WIL_Pycro_Control_App/utils/pycro.py:25-26"),
        Fact("init_logger creates a logs directory in the current directory and calls logging.basicConfig with a "
             "DEBUG log file there", source="upstream_code",
             ref="WIL_Pycro_Control_App/utils/init_logger.py:11-16"),
        Fact("_abort_acquisition, called when an acquisition is aborted or fails, stops sequence acquisition, clears "
             "the circular buffer, sets the default camera properties and resets the joystick", source="upstream_code",
             ref="WIL_Pycro_Control_App/acquisition/acquisition_class.py:182-196"),
    ]
    safe_state = ("None reached: the clone has no stage halt, so the e-stop sends nothing to the ASI console; the "
                  "MHS latch refuses new commands while a move already sent continues to its target. reset_stage "
                  "(RESET) is not sent: its docstring says it resets the console's flash memory, origin and joystick "
                  "settings, it is marked deprecated, and it is sent only after the XY stage stops being busy "
                  "(stage.py:51-57, 321-334).")

    # -- reads ------------------------------------------------------------------------------------------------
    @read("x_position", unit="um", type="integer", description="X position of the XY stage in micrometres")
    def x_position(self):
        return int(self.native.get_x_position())

    @read("y_position", unit="um", type="integer", description="Y position of the XY stage in micrometres")
    def y_position(self):
        return int(self.native.get_y_position())

    @read("z_position", unit="um", type="integer", description="Z position of the focus device in micrometres")
    def z_position(self):
        return int(self.native.get_z_position())

    # -- position writes ----------------------------------------------------------------------------------------
    @write("x_position", unit="um", type="integer",
           description="Move the XY stage X axis to a position in micrometres",
           limit=Limit.operator_required(_X_REASON))
    def set_x_position(self, value):
        self.native.set_x_position(int(value))
        return int(self.native.get_x_position())

    @write("y_position", unit="um", type="integer",
           description="Move the XY stage Y axis to a position in micrometres",
           limit=Limit.operator_required(_Y_REASON))
    def set_y_position(self, value):
        self.native.set_y_position(int(value))
        return int(self.native.get_y_position())

    @write("z_position", unit="um", type="integer",
           description="Move the focus device to a position in micrometres",
           limit=Limit.operator_required(_Z_REASON))
    def set_z_position(self, value):
        self.native.set_z_position(value)
        self.native.wait_for_z_stage()
        return int(self.native.get_z_position())

    # -- focus action -------------------------------------------------------------------------------------------
    @action(cap="cap.imaging.focus.v1", cancellable=True,
            description="Move the focus device to a target Z with the clone's set_z_position, or query the current "
                        "Z with method none; the clone has no autofocus routine",
            input={
                "method": Field("string", enum=["manual", "none"],
                                description="manual moves to target_z; none reads the current Z without motion"),
                "target_z": Field("number", unit="um",
                                  description="Target Z position of the focus device in micrometres",
                                  limit=Limit.operator_required(_TARGET_Z_REASON)),
            })
    def focus(self, method, target_z=None):
        if method == "none":
            self.check_cancelled()
            return {"focused": False, "z_um": float(self.native.get_z_position())}
        if method != "manual":
            raise DriverFailed("MHS.DEVICE.PRECONDITION_UNMET",
                               f"focus method {method!r} is not available in this clone; use manual or none")
        if target_z is None:
            raise DriverFailed("MHS.DEVICE.PRECONDITION_UNMET", "method manual needs target_z")
        self.check_cancelled()
        self.native.set_z_position(target_z)
        self.native.wait_for_z_stage()
        self.check_cancelled()
        return {"focused": False, "z_um": float(self.native.get_z_position())}

    # -- safety -------------------------------------------------------------------------------------------------
    @estop
    def stop(self):
        """Send nothing and refuse to certify a stop: the clone has none (model review, 2026-11-05).

        The runtime has latched first.  reset_stage is not a stop: it sends the ASI RESET command
        (flash memory, origin and joystick settings; marked deprecated, stage.py:321-334) through
        send_serial_command_to_stage, which first waits for the XY stage to stop being busy
        (stage.py:51-57), so it cannot interrupt an XY move, and the background retry of a failed
        e-stop would send it again every few seconds.  The e-stop reports SAFE_STATE_UNREACHED and
        the latch stays held.
        """
        raise DriverFailed(
            "MHS.SAFETY.SAFE_STATE_UNREACHED",
            "the clone has no stage halt command: nothing was sent to the ASI console, so a move already sent "
            "continues; reset_stage (RESET) resets flash memory, the origin and the joystick settings and waits for "
            "the XY stage first (stage.py:51-57, 321-334), so it is not used as a stop",
        )
