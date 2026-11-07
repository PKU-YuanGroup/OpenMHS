"""ROS-free F0 fake for the mrw-code/ros_morphology_robot v2 control window.

The fake keeps only the surface the driver uses: the upstream ``ControlWindow``
methods for opening the serial port, calibration, XY home and the six manual
single-axis moves, plus the GUI step-size spin box and the ``serial.Serial``
object those methods call.  It writes the same G-code byte strings into an
in-memory log; it does not open a port, run G-code, move a stage, capture an
image or contact ROS.

Every starting value and reply below is test data, not a device fact.
"""


class _Arduino:
    """The small part of ``serial.Serial`` the upstream control window uses."""

    def __init__(self):
        self.port = ""              # placeholder
        self.baudrate = 115200      # placeholder
        self._is_open = False
        self.written = []           # placeholder capture of one-way writes

    def open(self):
        self._is_open = True

    def close(self):
        self._is_open = False

    def isOpen(self):
        return self._is_open

    def write(self, data):
        if not self._is_open:
            raise OSError("the fake serial port is closed")
        self.written.append(bytes(data))


class _Spin:
    """The value/text part of the upstream ``QDoubleSpinBox`` step-size field."""

    def __init__(self, minimum=0.0, maximum=100.0):
        self.minimum = minimum
        self.maximum = maximum
        self._value = 0.0          # placeholder

    def setValue(self, value):
        # A QDoubleSpinBox holds the nearest value inside its own bounds.
        self._value = min(self.maximum, max(self.minimum, float(value)))

    def value(self):
        return self._value

    def textFromValue(self, value):
        # Locale formatting is deliberately not reproduced; this is test data.
        return f"{float(value):g}"


class _ExplorationThread:
    """The part of the upstream QThread the Exit path stops."""

    def __init__(self):
        self.ThreadActive = False

    def stop(self):
        self.ThreadActive = False


class FakeRosMorphologyRobot:
    def __init__(self, **_options):
        self.arduino = _Arduino()
        self.spinManualStepSize = _Spin()
        self.explorationThread = _ExplorationThread()
        # Placeholder starting state: a bench that has already been connected and calibrated.
        self.portConnectStatus = True
        self.systemCalibrate = True
        self.arduino.open()
        self.last_command = ""           # placeholder: last one-way G-code write
        self.last_move = None            # placeholder: (axis, signed_gui_step)
        self.window_closed = False       # placeholder: the upstream Exit path closes the Qt window

    def portConnection(self):
        if not self.portConnectStatus:
            self.arduino.open()
            if self.arduino.isOpen():
                self.portConnectStatus = True
        else:
            self.arduino.close()
            if not self.arduino.isOpen():
                # As upstream (control.py:401-414): closing clears the status and the calibration flag.
                self.portConnectStatus = False
                self.systemCalibrate = False

    def calibrateMotorSystem(self):
        if self.arduino.isOpen():
            self.arduino.write(b"$X\n")
            self.arduino.write(b"G10 P0 L20 X0 Y0 Z0\n")
            self.systemCalibrate = True

    def manualMotorControlHOME(self):
        if self.arduino.isOpen() and self.systemCalibrate:
            self.arduino.write(b"G90 G0 X0 Y0\n")
            self.last_command = "G90 G0 X0 Y0\n"

    def _move(self, axis, sign):
        if not self.arduino.isOpen():
            return
        step = self.spinManualStepSize.value() / 100.0
        command = "$J=G21G91" + axis + ("-" if sign < 0 else "") + self.spinManualStepSize.textFromValue(step) + "F50\n"
        self.arduino.write(command.encode("ascii"))
        self.last_command = command
        self.last_move = (axis, sign * self.spinManualStepSize.value())

    def manualMotorControlXPositive(self):
        self._move("X", 1)

    def manualMotorControlXNegative(self):
        self._move("X", -1)

    def manualMotorControlYPositive(self):
        self._move("Y", 1)

    def manualMotorControlYNegative(self):
        self._move("Y", -1)

    def manualMotorControlZPositive(self):
        self._move("Z", 1)

    def manualMotorControlZNegative(self):
        self._move("Z", -1)

    def quitSystem(self):
        # As upstream (control.py:454-457): no write to the controller, and portConnectStatus is left as it was.
        self.explorationThread.stop()
        self.arduino.close()
        self.window_closed = True        # placeholder for the upstream self.close() of the Qt window
