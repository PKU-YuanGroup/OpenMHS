"""Fake backend of the Runze syringe-pump driver: an in-memory stand-in for RunzeSyringePump.

The upstream class (``runze_backbone.py:80``) owns a pyserial link in ``self.hardware_interface`` and implements
the protocol as methods on the class.  This fake implements the same public method names and the private
``_query`` method the driver's e-stop path uses (gate G7 compares them with the clone's AST), and keeps the same
constructor attributes.  It never talks to a device.

Every number and reply below is canned test data, marked ``# placeholder``: the starting plunger position, the
25 mL modelled syringe, the step count, the valve label and all query strings are not facts, limits or references,
and this is not a recording.  Motion is modelled as five short chunks so that the ``T`` stop can interrupt a move
and leave the plunger part-way; it is deliberately not an instant state change.

Upstream semantics the fake keeps (model review): a move holds ``_run_lock`` as the upstream ``_run`` does
(runze_backbone.py:152-164), so ``stop_operation`` waits behind it; ``T`` ends only the move in progress and a move
command sent after it runs (the conservative reading: the clone documents no Runze command and nothing in it shows
``T`` holding a later command); and ``set_max_velocity``/``get_max_velocity`` use the upstream integer pulse
frequency (runze_backbone.py:225-236), so a velocity reads back truncated to a whole pulse frequency.
"""

import threading
import time

#: seconds one modelled move takes, split into five chunks (test data, not a device timing)
MOVE_TIME_S = 0.10  # placeholder


class FakeRunzeSyringePump:
    def __init__(self, **_options):
        self.port = str(_options.get("port", "/dev/fake-runze"))        # placeholder
        self.address = str(_options.get("address", "1"))                # placeholder
        self.max_volume = float(_options.get("max_volume_ml", 25.0))    # placeholder: modelled syringe
        self.total_steps = 6000                                          # placeholder
        self.total_steps_vel = 6000                                      # placeholder
        self._status = "Idle"                                            # placeholder: start status
        self._mode = None                                                # placeholder
        self._max_velocity = 0.0                                         # placeholder: start velocity, mL/s
        self._valve_position = "I"                                       # placeholder: start valve label
        self._steps = self.total_steps // 2                              # placeholder: start position
        self.hardware_interface = None                                   # placeholder: no serial link
        self._busy = False
        self._closing = False
        self._error_event = threading.Event()
        self._query_lock = threading.Lock()
        self._run_lock = threading.Lock()
        self._halt = threading.Event()
        self._grade = "0"                                                # placeholder
        self._pulse_freq = 0                                             # placeholder: start pulse frequency
        self.move_time_s = MOVE_TIME_S                                   # placeholder: tests may lengthen a move

    # -- properties of the upstream class ------------------------------------------------------------------------
    @property
    def status(self):
        return self._status

    @property
    def mode(self):
        return self._mode

    @property
    def max_velocity(self):
        return self._max_velocity

    @property
    def valve_position(self):
        return self._valve_position

    @property
    def position(self):
        return self._position_ml()

    # -- query path ----------------------------------------------------------------------------------------------
    def _query(self, command):
        with self._query_lock:
            if self._closing:
                raise RuntimeError("the fake pump is closing")
            if command == "T":
                self._halt.set()
                return "`"
            if command == "Q":
                return "`" if self._status == "Idle" else "a"
            return "`"

    def send_command(self, full_command):
        raise RuntimeError("the fake does not model the serial line; use the named methods")

    # -- status ---------------------------------------------------------------------------------------------------
    def get_status(self):
        self._status = "Busy" if self._busy else "Idle"
        return self._status

    # -- velocity -------------------------------------------------------------------------------------------------
    def set_max_velocity(self, velocity):
        # the upstream arithmetic (runze_backbone.py:225-229): an integer pulse frequency capped at 6000
        self._max_velocity = float(velocity)
        self._pulse_freq = min(6000, int(float(velocity) / self.max_volume * self.total_steps_vel))

    def get_max_velocity(self):
        # the upstream readback (runze_backbone.py:231-236)
        self._max_velocity = self._pulse_freq / self.total_steps_vel * self.max_volume
        return self._max_velocity

    def set_velocity_grade(self, velocity):
        self._grade = str(velocity)

    def get_velocity_grade(self):
        return self._grade

    def get_velocity_init(self):
        return 0, self._max_velocity

    def get_velocity_end(self):
        return 0, self._max_velocity

    # -- position -------------------------------------------------------------------------------------------------
    def set_position(self, position, max_velocity=None):
        if max_velocity is not None:
            self.set_max_velocity(max_velocity)
        target = int(float(position) / self.max_volume * self.total_steps)
        self._move(target - self._steps)

    def pull_plunger(self, volume):
        steps = int(float(volume) / self.max_volume * self.total_steps)
        self._move(steps)

    def push_plunger(self, volume):
        steps = int(float(volume) / self.max_volume * self.total_steps)
        self._move(-steps)

    def get_position(self):
        return self._position_ml()

    def get_plunger_position(self):
        return self._position_ml()

    # -- valve ----------------------------------------------------------------------------------------------------
    def set_valve_position(self, position):
        self._valve_position = str(position).upper()

    def get_valve_position(self):
        return self._valve_position

    # -- other upstream commands ----------------------------------------------------------------------------------
    def initialize(self):
        self._steps = 0
        self._status = "Idle"
        return "`"

    def set_baudrate(self, baudrate):
        if baudrate not in (9600, 38400):
            raise ValueError("Unsupported baudrate")
        return "`"

    def stop_operation(self):
        # upstream: self._run("T") (runze_backbone.py:352-353), which waits for _run_lock behind a running move
        with self._run_lock:
            self._halt.set()
            self._busy = False
            self._status = "Idle"
        return "`"

    def query_command_buffer_status(self):
        return "`0000"                                                  # placeholder

    def query_backlash_position(self):
        return "`0000"                                                  # placeholder

    def query_aux_input_status_1(self):
        return "`0"                                                     # placeholder

    def query_aux_input_status_2(self):
        return "`0"                                                     # placeholder

    def query_software_version(self):
        return "`V0.0"                                                  # placeholder

    def wait_error(self):
        return self._error_event.wait()

    def close(self):
        if self._closing:
            raise RuntimeError("the fake pump is already closing")
        self._closing = True
        self.hardware_interface = None

    # -- helpers --------------------------------------------------------------------------------------------------
    def _position_ml(self):
        return self._steps / self.total_steps * self.max_volume

    def _move(self, delta_steps):
        # A move holds _run_lock like the upstream _run; T ends only the move in progress, so a T sent before this
        # move started does not hold it (conservative: nothing in the clone shows T holding a later command).
        with self._run_lock:
            self._halt.clear()
            target = self._steps + int(delta_steps)
            self._busy = True
            self._status = "Busy"
            chunk = abs(int(delta_steps)) / 5.0
            try:
                for _ in range(5):
                    if self._halt.is_set():
                        return False
                    if self._steps < target:
                        self._steps = int(min(target, self._steps + chunk))
                    else:
                        self._steps = int(max(target, self._steps - chunk))
                    time.sleep(self.move_time_s / 5.0)
                if self._halt.is_set():
                    return False
                self._steps = target
                return True
            finally:
                self._busy = False
                self._status = "Idle"
