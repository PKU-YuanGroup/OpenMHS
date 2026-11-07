"""OpenMHS driver for gh.thedeanlab/navigate: the ASI MS-2000 motorised microscope stage.

A direct Driver (decorated methods) over the upstream device class
navigate.model.devices.stage.asi:MS2000Stage.  The stage class talks to the device through an ASI Tiger
controller object (``self.asi_controller``, stage/asi.py:680), so the native backend is a factory that opens
that controller and builds the class (native.py).

* reads: the x, y and z axis positions in micrometres.  ``get_axis_position`` asks the controller for the
  position in micrometres (``get_axis_position_um``, stage/asi.py:226) and the stage holds its positions in
  microns (stage/base.py:146-149);
* one extension action moves one axis to an absolute target in micrometres.  No text of the clone states a
  travel bound: the stage takes ``x_min``/``x_max`` per axis from the microscope configuration
  (stage/base.py:150-158), which is an operator property of the bench, so the target is
  ``Limit.operator_required`` and every move is refused ``MHS.SAFETY.LIMITS_UNSET`` until the site overlay
  supplies the range;
* one extension action stops a running line scan (the native ``stop_scan``);
* the native stop (``stop()``, stage/asi.py:380-383) is the e-stop and halts every axis.

The clone is a light-sheet microscope control framework with several device families; this package implements
only the first entry symbol of the card, MS2000Stage.  The other entry symbols (MFC2000Stage, XCaliburPump,
LuxxLaser, SyntheticCamera) are not covered here.

Every Fact cites a line of the clone at the pinned commit (da14920d7b40d048a5d2225a7846d11f78e05212).  This
package is model-authored and unreviewed: it is checked on the fake backend only (README.md).
"""

from mhs.driver import Driver, DriverFailed, Fact, Field, Limit, action, estop, read


class MS2000(Driver):
    device_id = "asi-ms2000"
    device_kind = "optics.stage"
    mode = "hardware"
    risk = "R1"
    native = "navigate.model.devices.stage.asi:MS2000Stage"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeMS2000Stage"}
    vendor, model = "Applied Scientific Instrumentation", "MS-2000"
    display_name = "ASI MS-2000 motorised stage (navigate.MS2000Stage)"
    tags = ["stage", "microscope", "motion", "serial", "asi"]
    facts = [
        Fact("MS2000Stage maps the software axes x, y and z to the controller axes X, Y and Z by default",
             source="upstream_code", ref="src/navigate/model/devices/stage/asi.py:656-662"),
        Fact("get_axis_position asks the controller for the axis position in micrometres "
             "(get_axis_position_um) and returns inf when the axis has no mapping",
             source="upstream_code", ref="src/navigate/model/devices/stage/asi.py:224-232"),
        Fact("The stage holds its axis positions in microns (x_pos, y_pos, ...; 'All units are in microns')",
             source="upstream_code", ref="src/navigate/model/devices/stage/base.py:146-149"),
        Fact("The per-axis travel bounds x_min and x_max are read from the microscope stage configuration",
             source="upstream_code", ref="src/navigate/model/devices/stage/base.py:150-158"),
        Fact("move_axis_absolute sends the target multiplied by 10 because the ASI controller unit is "
             "1/10 micrometre", source="upstream_code",
             ref="src/navigate/model/devices/stage/asi.py:288-293"),
        Fact("move_absolute takes positions in micrometres for the ASI API",
             source="upstream_code", ref="src/navigate/model/devices/stage/asi.py:335-345"),
        Fact("stop() sends the controller stop command and aborts all stage movement",
             source="upstream_code", ref="src/navigate/model/devices/stage/asi.py:380-383"),
        Fact("stop_scan() sends the controller scan stop command", source="upstream_code",
             ref="src/navigate/model/devices/stage/asi.py:580-584"),
        Fact("connect() opens the Tiger controller over serial for the stage", source="upstream_code",
             ref="src/navigate/model/devices/stage/asi.py:723-746"),
    ]
    safe_state = "all stage axes halted (the ASI controller stop command)"

    # -- reads ------------------------------------------------------------------------------------------------
    @read("x_position", unit="um", description="X axis position in micrometres")
    def x_position(self):
        return self.native.get_axis_position("x")

    @read("y_position", unit="um", description="Y axis position in micrometres")
    def y_position(self):
        return self.native.get_axis_position("y")

    @read("z_position", unit="um", description="Z axis position in micrometres")
    def z_position(self):
        return self.native.get_axis_position("z")

    # -- actions ----------------------------------------------------------------------------------------------
    @action(name="x-cap.thedeanlab.move_axis_absolute.v1",
            description="Move one stage axis to an absolute position in micrometres",
            input={
                "axis": Field("string", enum=["x", "y", "z"],
                              description="Software stage axis to move (x, y or z)"),
                "position": Field("number", unit="um",
                                  description="Absolute target position of the axis in micrometres",
                                  limit=Limit.operator_required(
                                      "the axis travel range is a property of the installed stage and its site "
                                      "microscope configuration (x_min/x_max, stage/base.py:150-158); no text of "
                                      "the clone states one, so the site supplies it")),
            },
            output={
                "axis": Field("string", description="The axis that was moved"),
                "position": Field("number", unit="um",
                                  description="Absolute position the axis reports after the move"),
            })
    def move_axis_absolute(self, axis, position):
        moved = self.native.move_axis_absolute(axis, position, wait_until_done=True)
        if not moved:
            raise DriverFailed("MHS.DEVICE.FAULTED",
                               f"move_axis_absolute({axis!r}, {position!r}) returned False")
        return {"axis": axis, "position": self.native.get_axis_position(axis)}

    @action(name="x-cap.thedeanlab.stop_scan.v1",
            description="Stop a running line scan (the native scan stop); it takes no input",
            output={"stopped": Field("boolean", description="True once the scan stop was sent")})
    def stop_scan(self):
        self.native.stop_scan()
        return {"stopped": True}

    # -- safety -----------------------------------------------------------------------------------------------
    @estop
    def stop(self):
        """The native stop: the runtime latches first, then this halts every axis."""
        self.native.stop()
