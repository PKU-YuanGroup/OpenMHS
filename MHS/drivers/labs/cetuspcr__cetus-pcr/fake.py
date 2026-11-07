"""Fake backend of the Cetus PCR driver: an in-memory stand-in for functions:ArduinoPCR.

Gate G7: the public methods here (``initialize_connection``, ``serial_monitor`` and ``run_experiment``) are the
public methods of the upstream class functions.py:72-262.  The driver reaches only attributes that class sets in
``__init__`` (functions.py:75-113) and the nested ``serial_device`` object the upstream opens in
``initialize_connection`` (functions.py:241-243).  The nested pyserial-like object is not part of the backend class,
so it is not part of the checked fake surface.

The fake mirrors the cancellation path of the upstream loop: ``run_experiment`` returns when ``is_running`` is
cleared and writes ``<peltier 0 0>`` through the fake serial device (functions.py:137-144).  The zero-PWM command is
the only thing the driver writes to the device, because this package uses the upstream PID loop for actuation and
never sends a raw PWM value itself.

Every starting number is test data, not a fact about the machine, and is marked ``# placeholder``.  Nothing here
talks to a device.
"""


class _FakeSerial:
    """The pyserial-like object the upstream ``initialize_connection`` would open; it records writes."""

    def __init__(self, owner):
        self._owner = owner
        self.written = []
        self.is_open = True

    def write(self, data):
        payload = bytes(data)
        self.written.append(payload)
        if payload == b"<peltier 0 0>":
            self._owner.heater_pwm = 0
            self._owner.cooler_pwm = 0
        return len(payload)

    def readline(self):
        return b"Cetus is ready.\r\n"

    def close(self):
        self.is_open = False


class FakeCetusPcr:
    """A Cetus PCR controller that connects immediately and completes a hold loop without waiting."""

    def __init__(self, **_options):
        self.timeout = 1                                   # placeholder: constructor value, not a device bound
        self.baudrate = 9600                               # placeholder: constructor value, not a device bound
        self.experiment = None
        self.cooling_experiment = None
        self.device_type = ""
        self.port_connected = None
        self.serial_device = None
        self.is_connected = False
        self.waiting_update = False
        self.monitor_thread = None
        self.is_running = False
        self.is_waiting = True
        self.current_sample_temperature = 25.0             # placeholder: start temperature
        self.current_lid_temperature = 30.0                # placeholder: start temperature
        self.current_step = ""
        self.current_step_temp = 0
        self.current_cycle = 0
        self.elapsed_time = 0
        self.is_cooling = False
        self.reading = ""
        self.heater_pwm = 0                                # placeholder: no drive before the first command
        self.cooler_pwm = 0                                # placeholder: no drive before the first command

    # -- the upstream public methods -------------------------------------------------
    def initialize_connection(self):
        if self.is_connected:
            return
        self.serial_device = _FakeSerial(self)
        self.is_connected = True
        self.port_connected = "fake"

    def serial_monitor(self):
        """The upstream monitor thread runs until is_connected clears; the fake has nothing to read."""
        return

    def run_experiment(self):
        """Complete the configured steps immediately; stop early when is_running is cleared."""
        if not self.is_running or self.experiment is None:
            self._peltier_off()
            return
        self.elapsed_time = 0
        for cycle in range(int(self.experiment.n_cycles)):
            if not self.is_running:
                self._peltier_off()
                return
            self.current_cycle = cycle + 1
            for step in self.experiment.steps:
                if not self.is_running:
                    self._peltier_off()
                    return
                self.current_step = str(step.name)
                self.current_step_temp = float(step.temperature)
                self.current_sample_temperature = float(step.temperature)
                self.elapsed_time += int(step.duration)
        self.is_waiting = True

    def _peltier_off(self):
        if self.serial_device is not None:
            self.serial_device.write(b"<peltier 0 0>")
        self.heater_pwm = 0
        self.cooler_pwm = 0
