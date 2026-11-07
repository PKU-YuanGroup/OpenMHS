"""Fake backend of the PyAPT driver: an in-memory stand-in for PyAPT.PyAPT:APTMotor.

Gate G7: every public method defined here exists on PyAPT.PyAPT:APTMotor in the clone, and the attributes the driver
reaches are set by the upstream __init__: ``aptdll`` (PyAPT/PyAPT.py:48), ``SerialNum`` and ``HWType``
(PyAPT/PyAPT.py:52-56), ``Connected`` (PyAPT/PyAPT.py:45) and ``blCorr`` (PyAPT/PyAPT.py:53).  The upstream class
talks to Thorlabs APT.dll; this stand-in keeps the stage state in memory and never imports the clone or touches
hardware.  Every starting value is test data, not a fact about any stage, and is marked ``# placeholder``.  The
stand-in does not model the APT wire protocol, motion kinematics, the controller's own travel-range check, the
configured homing profile or the meaning of the limit-switch modes beyond the values the driver reads.
"""


class _FakeAPTDDLL:
    """The part of the APT.dll handle the driver reaches through the upstream object's ``aptdll`` attribute."""

    def __init__(self, motor):
        self._motor = motor

    def MOT_StopProfiled(self, serial_number):
        self._motor._stop_count += 1

    def APTCleanUp(self):
        self._motor._cleaned = True


class FakeAPTMotor:
    def __init__(self, **_options):
        self.verbose = False                    # placeholder
        self.Connected = True                   # placeholder: the fake stands in for an initialised controller
        self.SerialNum = 0                      # placeholder
        self.HWType = 31                        # placeholder: the upstream constructor default
        self.blCorr = 0.10                      # placeholder: the upstream constructor default
        self.aptdll = _FakeAPTDDLL(self)
        self._position = 1.0                    # placeholder: starting position in stage units
        self._minimum_velocity = 0.0            # placeholder
        self._acceleration = 0.1                # placeholder: stage units per second squared
        self._maximum_velocity = 0.2           # placeholder: stage units per second
        self._maximum_acceleration = 1.0        # placeholder: controller limit of this stand-in
        self._maximum_velocity_allowed = 1.0    # placeholder: controller limit of this stand-in
        self._stage_minimum = -1.0e9            # placeholder: the stand-in adds no travel bound of its own
        self._stage_maximum = 1.0e9             # placeholder: the stand-in adds no travel bound of its own
        self._stage_units = 1                   # placeholder: the stand-in reports one unit code
        self._pitch = 1.0                       # placeholder
        self._reverse_limit_switch = 1          # placeholder
        self._forward_limit_switch = 1          # placeholder
        self._stop_count = 0                    # placeholder
        self._cleaned = False                   # placeholder

    # -- reads ---------------------------------------------------------------------------------------------
    def getPos(self):
        if not self.Connected:
            raise RuntimeError("Please connect first! Use initializeHardwareDevice")
        return self._position

    def getStageAxisInformation(self):
        return [self._stage_minimum, self._stage_maximum, self._stage_units, self._pitch]

    def getVelocityParameters(self):
        return [self._minimum_velocity, self._acceleration, self._maximum_velocity]

    def getVelocityParameterLimits(self):
        return [self._maximum_acceleration, self._maximum_velocity_allowed]

    def getHardwareLimitSwitches(self):
        return [self._reverse_limit_switch, self._forward_limit_switch]

    def getHardwareInformation(self):
        return ["fake APT controller", "fake firmware", "fake stand-in"]  # placeholder

    def getNumberOfHardwareUnits(self):
        return 1                                # placeholder

    def getSerialNumberByIdx(self, index):
        return self.SerialNum

    def getVel(self):
        return self.getVelocityParameters()[2]

    # -- writes and actions --------------------------------------------------------------------------------
    def setSerialNumber(self, SerialNum):
        self.SerialNum = int(SerialNum)
        return self.SerialNum

    def initializeHardwareDevice(self):
        self.Connected = True
        return True

    def mAbs(self, absPosition):
        if not self.Connected:
            raise RuntimeError("Please connect first! Use initializeHardwareDevice")
        self._position = float(absPosition)
        return True

    def mRel(self, relDistance):
        if not self.Connected:
            raise RuntimeError("Please connect first! Use initializeHardwareDevice")
        self._position += float(relDistance)
        return True

    def go_home(self):
        if not self.Connected:
            raise RuntimeError("Please connect first! Use initializeHardwareDevice")
        self._position = 0.0                    # placeholder: home position of the stand-in
        return True

    def setVelocityParameters(self, minVel, acc, maxVel):
        self._minimum_velocity = float(minVel)
        self._acceleration = float(acc)
        self._maximum_velocity = float(maxVel)
        return True

    def setVel(self, maxVel):
        minimum_velocity, acceleration, _maximum_velocity = self.getVelocityParameters()
        self.setVelocityParameters(minimum_velocity, acceleration, maxVel)
        return True

    def identify(self):
        return True

    def cleanUpAPT(self):
        self.aptdll.APTCleanUp()
        self.Connected = False
