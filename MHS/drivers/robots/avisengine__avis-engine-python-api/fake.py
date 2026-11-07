"""Fake backend of the AVIS Engine driver: an in-memory stand-in for ``avisengine:Car``.

Gate G7: every public member defined here is a method of ``Car`` (avisengine.py at the pinned commit
32b9a9e063a5608b9b60a87aa32171d44c116316): ``setSpeed``, ``setSteering``, ``setSensorAngle``, ``getData``,
``getSensors``, ``getSpeed``, ``updateData`` and ``stop``, with the upstream parameter names.  The state lives in
plain attributes that the upstream class also declares (``speed_value``, ``steering_value``, ``sensor_angle``,
``sensors``, ``current_speed``).

What it does not do: no socket, no TCP connection to the simulator, no ``<EOF>`` framing, no base64 image decoding
and no vehicle dynamics.  ``getData`` returns placeholder readings immediately, ``setSpeed`` makes the placeholder
speed follow the throttle command, and ``stop`` zeroes the commands and records the stop.  Every number below is
test data, not a device fact: each one is marked ``# placeholder`` and none is used in a Fact, a Limit or a
reference.  The real image array from ``Car.getImage`` is not modelled (see the driver's fidelity gaps and
RESULT.json).
"""

#: The upstream fallback for a reply without a <sensor> tag (avisengine.py:168), used here as test data.
SENSOR_PLACEHOLDER_CM = 1500                          # placeholder
#: The class default of Car.sensor_angle (avisengine.py:45), used here as a starting value.
START_SENSOR_ANGLE_DEG = 30                           # placeholder
SENSOR_COUNT = 3                                      # placeholder: left, middle, right
#: The text-command shape of avisengine.py:51, kept so ``data_str`` looks like the upstream request.
DATA_FORMAT = "Speed:{},Steering:{},ImageStatus:{},SensorStatus:{},GetSpeed:{},SensorAngle:{}"


class FakeCar:
    """A synchronous stand-in for ``Car`` with no transport (see the module docstring)."""

    def __init__(self, **_options):
        self.steering_value = 0                        # placeholder
        self.speed_value = 0                           # placeholder
        self.sensor_status = 1                         # placeholder
        self.image_mode = 1                            # placeholder
        self.get_Speed = 1                             # placeholder
        self.sensor_angle = START_SENSOR_ANGLE_DEG     # placeholder
        self.sensors = [SENSOR_PLACEHOLDER_CM] * SENSOR_COUNT   # placeholder
        self.current_speed = 0                         # placeholder
        self.image = None
        self.data_str = DATA_FORMAT.format(0, 0, 1, 1, 1, START_SENSOR_ANGLE_DEG)   # placeholder values
        self._commands: list[tuple[str, object]] = []
        self._stop_calls = 0
        self._stopped = False
        self._closed = False

    # -- controls ------------------------------------------------------------------------------------------------
    def setSpeed(self, speed):
        self._commands.append(("setSpeed", speed))
        self.speed_value = int(speed)
        self.image_mode = 0
        self.sensor_status = 0
        self.updateData()

    def setSteering(self, steering):
        self._commands.append(("setSteering", steering))
        self.steering_value = int(steering)
        self.image_mode = 0
        self.sensor_status = 0
        self.updateData()

    def setSensorAngle(self, angle):
        self._commands.append(("setSensorAngle", angle))
        self.sensor_angle = int(angle)
        self.image_mode = 0
        self.sensor_status = 0
        self.updateData()

    # -- data ----------------------------------------------------------------------------------------------------
    def getData(self):
        self._commands.append(("getData", None))
        self.image_mode = 1
        self.sensor_status = 1
        self.updateData()
        # placeholder: no vehicle dynamics, so the reported speed simply follows the throttle command
        self.current_speed = int(self.speed_value)
        self.sensors = [SENSOR_PLACEHOLDER_CM] * SENSOR_COUNT   # placeholder

    def getSensors(self):
        return list(self.sensors)

    def getSpeed(self):
        return self.current_speed

    def updateData(self):
        self.data_str = DATA_FORMAT.format(self.speed_value, self.steering_value, self.image_mode,
                                           self.sensor_status, self.get_Speed, self.sensor_angle)

    # -- stop ----------------------------------------------------------------------------------------------------
    def stop(self):
        self._commands.append(("stop", None))
        self._stop_calls += 1
        self.setSpeed(0)
        self.setSteering(0)
        self.current_speed = 0                          # placeholder
        self._stopped = True
        self._closed = True
