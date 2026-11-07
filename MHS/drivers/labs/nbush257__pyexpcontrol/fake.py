"""Fake backend of the pyexpcontrol driver: an in-memory stand-in for nebPod:Controller.

Gate G7: every public method defined here exists on ``nebPod:Controller`` in the clone (python/nebPod.py: 778, 793,
1691, 1715, 1739, 1954, 1243, 1267).  The fake keeps the commanded state in plain attributes and never talks to a
device.  The starting values are test data, not facts about any rig, and each is marked ``# placeholder``.  The
upstream methods mostly wait for a reply byte (``set_all_olfactometer_valves`` waits in ``wait_for_response``, and
the camera-trigger methods return without waiting); here each command returns immediately and records itself in
``calls`` so a test can see what reached the backend.
"""


class FakeController:
    def __init__(self, port="fake-port", gas_map=None, cobalt_mode="S", null_voltage=0.4, record_control="sglx",
                 **options):                                       # null_voltage 0.4: placeholder (upstream default)
        self.port = port
        self.gas_map = gas_map
        self.cobalt_mode = cobalt_mode
        self.null_voltage = null_voltage
        self.record_control = record_control
        self.calls = []
        self.laser_amplitude = 0.0          # placeholder
        self.laser_on = False               # placeholder
        self.valves = [False] * 8           # placeholder: all eight olfactometer valves closed
        self.gpio = ["low"] * 8             # placeholder: all eight GPIO pins low
        self.camera_fps = 0                 # placeholder: camera trigger not started
        self.camera_triggering = False      # placeholder

    def _record(self, name, *args):
        self.calls.append((name, args))

    def turn_on_laser(self, amp, verbose=False):
        self._record("turn_on_laser", amp)
        value = float(amp)
        value = 1.0 if value > 1 else 0.0 if value < 0 else value
        self.laser_amplitude = int(value * 100) / 100.0     # placeholder scale, as _amp2int does
        self.laser_on = True

    def turn_off_laser(self, amp, verbose=False):
        self._record("turn_off_laser", amp)
        self.laser_amplitude = 0.0          # placeholder
        self.laser_on = False

    def set_all_olfactometer_valves(self, binary_string, verbose=True):
        self._record("set_all_olfactometer_valves", binary_string)
        self.valves = [character == "1" for character in binary_string]

    def open_olfactometer(self, valve, verbose=True):
        self._record("open_olfactometer", valve)
        self.valves[int(valve) - 1] = True

    def close_olfactometer(self, valve, verbose=True):
        self._record("close_olfactometer", valve)
        self.valves[int(valve) - 1] = False

    def set_gpio(self, pin, mode, category="event", pulse_duration_sec=0.1, verbose=True):
        # pulse_duration_sec 0.1: placeholder (upstream default)
        self._record("set_gpio", pin, mode)
        self.gpio[int(pin)] = {"p": "pulse", "h": "high", "l": "low"}[str(mode)[0].lower()]

    def start_camera_trig(self, fps=120, verbose=False):
        # fps 120: placeholder (upstream default, not a fact about the camera)
        self._record("start_camera_trig", fps)
        self.camera_fps = int(fps)          # placeholder
        self.camera_triggering = True

    def stop_camera_trig(self, verbose=False):
        self._record("stop_camera_trig")
        self.camera_fps = 0                 # placeholder
        self.camera_triggering = False
