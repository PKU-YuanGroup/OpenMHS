"""OpenMHS driver for the mrw-code/ros_morphology_robot microscopy stage.

The pinned upstream is a Python/PyQt5 application, not a ROS motion node.  The
v2 control window opens a pyserial port and sends G-code strings to an Arduino
stage controller; the ROS 1 scripts carry only the inference trigger
(``do_inference_topic`` -> ``ready_move``).  A RosDriver around those topics
would replace the primary stage control with an auxiliary handshake, so this
package is a direct Driver over the final ``ControlWindow`` class and records
the deviation in RESULT.json.

Scope: the upstream manual single-axis relative moves, calibration and XY home
commands, plus the GUI step-size field.  The camera/JPG capture path and the
ROS inference handshake are not exposed here.  The upstream drives a real
Arduino G-code stage and has no simulator, no position feedback and no stop
command: ``quitSystem()`` stops the exploration thread and closes the serial
port and the window, but writes nothing to the controller, so moves it has
already received may continue.  The e-stop therefore runs that Exit path and
then reports MHS.SAFETY.SAFE_STATE_UNREACHED with the latch held (model review,
2026-11-05).  The card's mode is simulated, so the package serves only a
ROS-free F0 fake; no hardware backend or live ROS graph is opened.

Every Fact and Limit cites the pinned clone at
bdff1da251c4671dcbe94d7b6fa2d24e22459380.
"""

from mhs.driver import Driver, DriverFailed, Fact, Field, Limit, action, estop, read, write

#: The upstream class lives in the final v2 tree.
_NATIVE = "v2_robot.src.robot_v2.scripts.src.control:ControlWindow"

#: GUI step-size spin box: minimum 0.0 and maximum 100.0 (control.py:152-153).
_STEP_REF = "v2_robot/src/robot_v2/scripts/src/control.py:152-153"

#: The same GUI value is divided by 100.0 before it enters the G-code command.
_STEP_DIVISOR_REF = "v2_robot/src/robot_v2/scripts/src/control.py:299-300"

#: One limit object is not shared between the writable state and the action
#: input because the manifest carries each binding separately.
def _step_limit() -> Limit:
    return Limit(min=0.0, max=100.0, unit="1", source="upstream_code", ref=_STEP_REF)


class RosMorphologyRobot(Driver):
    device_id = "ros-morphology-robot"
    device_kind = "instrument.microscope"
    mode = "simulated"
    risk = "R1"
    native = _NATIVE
    backends = {"fake": ".fake:FakeRosMorphologyRobot"}
    vendor = "mrw-code"
    model = "ros_morphology_robot v2"
    display_name = "mrw-code morphology microscopy stage (v2 control window)"
    tags = ["microscope", "morphology", "stage", "gcode", "serial", "ros1", "simulated"]
    facts = [
        Fact("README.md names v2_robot as the final version and robot/ as legacy code kept for completeness.",
             source="vendor_doc", ref="README.md:5"),
        Fact("portConnection sets the pyserial port and baudrate from the GUI fields and opens the port.",
             source="upstream_code", ref="v2_robot/src/robot_v2/scripts/src/control.py:384-388"),
        Fact("Closing the port through portConnection clears portConnectStatus and sets systemCalibrate to False.",
             source="upstream_code", ref="v2_robot/src/robot_v2/scripts/src/control.py:401-414"),
        Fact("The control window sets the relative-move speed string to 'F50\\n'.", source="upstream_code",
             ref="v2_robot/src/robot_v2/scripts/src/control.py:268"),
        Fact("The manual step-size spin box is bounded by setMinimum(0.0) and setMaximum(100.0).",
             source="upstream_code", ref="v2_robot/src/robot_v2/scripts/src/control.py:152-153"),
        Fact("A manual relative move writes '$J=G21G91' plus the axis, the spin box's textFromValue of the step "
             "value divided by 100.0 and speed_rel to the serial port, then sleeps 0.1 s.",
             source="upstream_code", ref="v2_robot/src/robot_v2/scripts/src/control.py:296-302"),
        Fact("Calibration writes '$X\\n' and 'G10 P0 L20 X0 Y0 Z0\\n' to an open serial port and sets the "
             "systemCalibrate software flag.", source="upstream_code",
             ref="v2_robot/src/robot_v2/scripts/src/control.py:367-380"),
        Fact("HOME writes 'G90 G0 X0 Y0\\n' only when the port is open and systemCalibrate is true; it does not "
             "home Z.", source="upstream_code",
             ref="v2_robot/src/robot_v2/scripts/src/control.py:356-365"),
        Fact("getMonitorSystemValues only prints '@GETALLPOS' to stdout; it writes nothing to the port and reads "
             "no reply.", source="upstream_code", ref="v2_robot/src/robot_v2/scripts/src/control.py:270-274"),
        Fact("quitSystem calls explorationThread.stop(), closes the serial port and closes the window; it writes "
             "no command to the controller.", source="upstream_code",
             ref="v2_robot/src/robot_v2/scripts/src/control.py:454-457"),
        Fact("The exploration stop() sets ThreadActive to false, joins the subscriber thread with timeout 0 and "
             "calls quit(); it writes nothing to the serial port.", source="upstream_code",
             ref="v2_robot/src/robot_v2/scripts/src/exploration.py:151-155"),
        Fact("The exploration run loop busy-waits in 'while config.pictureSaved == False' and 'while not "
             "self.shall_i_move' without checking ThreadActive.", source="upstream_code",
             ref="v2_robot/src/robot_v2/scripts/src/exploration.py:90-94"),
        Fact("After its row loops the exploration run writes 'G90 G0 X0 Y0' to the port.", source="upstream_code",
             ref="v2_robot/src/robot_v2/scripts/src/exploration.py:138-140"),
        Fact("The v2 ROS subscriber calls rospy.Subscriber on the relative name do_inference_topic (String) and "
             "rospy.Publisher on the relative name ready_move (Bool), then rospy.spin().",
             source="upstream_code", ref="v2_robot/src/robot_v2/scripts/subscriber.py:13-19"),
        Fact("QtCapture creates a publisher on the relative topic do_inference_topic, initialises the anonymous "
             "ROS node inference_trigger and opens the camera with cv2.VideoCapture(0).", source="upstream_code",
             ref="v2_robot/src/robot_v2/scripts/src/capture.py:41-51"),
        Fact("The exploration thread subscribes to the relative topic ready_move; its callback stores the Boolean "
             "in shall_i_move.", source="upstream_code",
             ref="v2_robot/src/robot_v2/scripts/src/exploration.py:50-57"),
        Fact("The ControlWindow constructor prints every serial port device it lists.", source="upstream_code",
             ref="v2_robot/src/robot_v2/scripts/src/control.py:49-52"),
    ]
    #: No acknowledged stop exists; this states what the e-stop leaves behind.
    safe_state = ("No acknowledged stop exists: the e-stop runs the upstream Exit path (exploration thread "
                  "stopped, serial port and window closed) and reports MHS.SAFETY.SAFE_STATE_UNREACHED with the "
                  "latch held. Nothing is sent to the G-code controller, so moves it has already received may "
                  "continue; nothing confirms that the stage stopped.")
    fidelity = {
        "engine": "analytic:ROS-free Python stand-in for the PyQt control window",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "none",
            "notes": "State-machine fake with placeholder positions and replies; no Qt event loop, serial port, "
                     "camera, G-code interpreter or ROS graph runs",
        },
        "timestep_ms": 0,
        "realtime_factor": 0,
        "reset": "none",
        "snapshot_restore": False,
        "gaps": [
            "the fake records G-code writes and updates placeholder GUI/axis state; it does not execute G-code, "
            "step a motor, capture an image or publish on ROS",
            "the upstream serial protocol is one-way in this path: there is no position, completion or stop "
            "acknowledgement to model",
            "the camera/JPG capture path and the do_inference_topic/ready_move handshake are not exposed",
            "no acknowledged stop: quitSystem writes no command to the controller, so the e-stop reports "
            "SAFE_STATE_UNREACHED; an exploration run that is busy-waiting for a picture or for ready_move does "
            "not see the stop flag, and its final home write fails only because the port is closed",
            "the real device is an Arduino G-code stage, not a simulator; the card's simulated mode comes from "
            "the registry record, and the upstream window needs a Qt display, prints to stdout (a risk for an "
            "MHS server on stdio) and must be calibrated again after the port is reopened",
            "the fake formats the divided step with %g; the upstream uses QDoubleSpinBox.textFromValue, whose "
            "decimals and locale (Qt, outside the clone; the clone sets no decimals) can round the value, so "
            "the exact G-code strings in the tests are fake-only",
        ],
    }

    # -- state -----------------------------------------------------------------------------------------------
    @read("step", unit="1", description="Manual step-size value held in the upstream GUI spin box")
    def get_step(self):
        return self.native.spinManualStepSize.value()

    @write("step", unit="1", description="Manual step-size value held in the upstream GUI spin box",
           limit=_step_limit())
    def set_step(self, value):
        self.native.spinManualStepSize.setValue(value)

    @read("port_open", type="boolean", description="True while the upstream pyserial port reports isOpen()")
    def get_port_open(self):
        return bool(self.native.arduino.isOpen())

    @read("calibration_flag", type="boolean",
          description="The upstream systemCalibrate software flag, not a sensed position")
    def get_calibration_flag(self):
        return bool(self.native.systemCalibrate)

    # -- helpers ---------------------------------------------------------------------------------------------
    def _ensure_connected(self):
        if bool(self.native.arduino.isOpen()):
            return
        # quitSystem() closes the port without clearing the upstream UI flag; toggle the
        # stale flag closed first, then open the port through the same upstream method.
        if bool(self.native.portConnectStatus):
            self.native.portConnection()
        if not bool(self.native.portConnectStatus):
            self.native.portConnection()
        if not bool(self.native.arduino.isOpen()):
            raise DriverFailed("MHS.DEVICE.NOT_READY", "the upstream serial port is not open")

    def _ensure_calibrated(self):
        self._ensure_connected()
        if not bool(self.native.systemCalibrate):
            raise DriverFailed("MHS.DEVICE.PRECONDITION_UNMET",
                               "the upstream stage is not calibrated; call calibrate first")

    # -- commands --------------------------------------------------------------------------------------------
    @action(name="x-cap.mrw-code.connect.v1",
            description="Open the upstream serial port if it is closed; no motion is commanded",
            output={"port_open": Field("boolean", description="True once the upstream port reports isOpen()")})
    def connect(self):
        self._ensure_connected()
        return {"port_open": bool(self.native.arduino.isOpen())}

    @action(name="x-cap.mrw-code.calibrate.v1",
            description="Run the upstream $X and G10 P0 L20 X0 Y0 Z0 calibration writes",
            output={"calibration_flag": Field("boolean",
                                              description="The upstream systemCalibrate flag after the writes")})
    def calibrate(self):
        self._ensure_connected()
        self.native.calibrateMotorSystem()
        if not bool(self.native.systemCalibrate):
            raise DriverFailed("MHS.DEVICE.PRECONDITION_UNMET", "the upstream calibration flag did not set")
        return {"calibration_flag": True}

    @action(name="x-cap.mrw-code.home.v1",
            description="Run the upstream 'G90 G0 X0 Y0' home command for the X and Y axes",
            output={"commanded": Field("boolean",
                                       description="True once the one-way home G-code write has been sent")})
    def home(self):
        self._ensure_calibrated()
        self.native.manualMotorControlHOME()
        return {"commanded": True}

    @action(name="x-cap.mrw-code.move_relative.v1",
            description="Command one relative single-axis step through the upstream manual-move method",
            input={
                "axis": Field("string", enum=["x", "y", "z"], description="Stage axis to move"),
                "direction": Field("string", enum=["positive", "negative"],
                                   description="Sign of the relative move"),
                "step": Field("number", unit="1",
                              description="GUI step-size value; the upstream divides it by 100.0 before G-code",
                              limit=_step_limit()),
            },
            output={
                "commanded": Field("boolean",
                                   description="True once the one-way G-code write has been sent"),
                "axis": Field("string", description="Axis named in the accepted command"),
                "direction": Field("string", description="Sign named in the accepted command"),
                "step": Field("number", unit="1", description="GUI step-size value that was written"),
            })
    def move_relative(self, axis, direction, step):
        self._ensure_connected()
        self.native.spinManualStepSize.setValue(step)
        method = {
            ("x", "positive"): self.native.manualMotorControlXPositive,
            ("x", "negative"): self.native.manualMotorControlXNegative,
            ("y", "positive"): self.native.manualMotorControlYPositive,
            ("y", "negative"): self.native.manualMotorControlYNegative,
            ("z", "positive"): self.native.manualMotorControlZPositive,
            ("z", "negative"): self.native.manualMotorControlZNegative,
        }[(axis, direction)]
        method()
        return {"commanded": True, "axis": axis, "direction": direction, "step": step}

    @action(name="x-cap.mrw-code.close_command_channel.v1",
            description="Run the upstream Exit path (stop the exploration thread, close the port); not a stop",
            output={"command_channel_closed": Field(
                "boolean", description="True when the upstream serial port reports closed")})
    def close_command_channel(self):
        self.native.quitSystem()
        return {"command_channel_closed": not bool(self.native.arduino.isOpen())}

    @estop
    def stop(self):
        """Run the upstream Exit path, then refuse to certify it.

        quitSystem() stops the exploration thread and closes the serial port and the window
        (control.py:454-457) but writes no command to the G-code controller, so moves it has
        already received may continue: the e-stop reports SAFE_STATE_UNREACHED and the latch
        stays held (model review, 2026-11-05).
        """
        self.native.quitSystem()
        raise DriverFailed(
            "MHS.SAFETY.SAFE_STATE_UNREACHED",
            "the upstream Exit path closed the serial port without sending any stop command; moves already "
            "received by the G-code controller may continue",
        )
