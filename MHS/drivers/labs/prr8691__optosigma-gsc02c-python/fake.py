"""Fake backend of the GSC-02C driver: an in-memory stand-in for optosigma_gsc02c.controller:GSC02C.

Gate G7: every public method defined here also exists on the upstream class.  The fake models the controller's
commanded-pulse coordinate, which is what the upstream class reports (optosigma_gsc02c/controller.py:328-332); it
builds no ASCII command and opens no serial port.  A move is applied immediately, so the busy flag is never observed
as true here.  All starting positions and speeds below are placeholders, not facts or limits of any device: they echo
the defaults of the upstream simulator (optosigma_gsc02c/simulated.py:13-14, 31) only so the driver has a state to
move.
"""


class FakeGSC02C:
    def __init__(self, **_options):
        self.axis = 1                        # placeholder
        self.um_per_pulse = 1.0              # placeholder: mirrors the StageConfig default
        self._min_pulses = 0                 # placeholder: mirrors the StageConfig default range
        self._max_pulses = 85000             # placeholder: mirrors the StageConfig default range
        self._position_pulses = 42500        # placeholder: the upstream simulator's initial position
        self._start_speed_mm_s = 0.5         # placeholder: the upstream simulator's default
        self._max_speed_mm_s = 10.0          # placeholder: the upstream simulator's default
        self._accel_time_ms = 200            # placeholder: the upstream simulator's default
        self._busy = False
        self._stopped = False
        self._connected = True               # placeholder: a served fake is ready to answer

    # -- connection --------------------------------------------------------------------------------------------
    def connect(self):
        self._connected = True

    def close(self):
        self._connected = False
        self._busy = False

    def _require_connection(self):
        if not self._connected:
            raise RuntimeError("Simulated controller is not connected.")

    # -- unit conversion ---------------------------------------------------------------------------------------
    def mm_to_pulses(self, distance_mm):
        pulse_mm = self.um_per_pulse / 1000.0
        return int(round(distance_mm / pulse_mm))

    def pulses_to_mm(self, pulses):
        return pulses * self.um_per_pulse / 1000.0

    def _check_pulses(self, pulses):
        if not (self._min_pulses <= pulses <= self._max_pulses):
            raise ValueError(
                f"Requested position {pulses} pulses is outside the "
                f"{self._min_pulses} to {self._max_pulses} pulse software limits."
            )

    # -- status and position -----------------------------------------------------------------------------------
    def raw_status(self):
        self._require_connection()
        # placeholder: the Q: reply is comma-separated; the driver only republishes it as a string
        return f"{self._position_pulses:+d},{0:+d}"  # placeholder: canned reply, second axis unused

    def is_busy(self):
        self._require_connection()
        return self._busy

    def get_position_pulses(self):
        self._require_connection()
        return self._position_pulses

    def get_position_mm(self):
        return self.pulses_to_mm(self.get_position_pulses())

    # -- speed / acceleration settings -------------------------------------------------------------------------
    def set_max_speed_mm_s(self, max_speed_mm_s, start_speed_mm_s=0.5, accel_time_ms=200):
        self._require_connection()
        if max_speed_mm_s <= 0:
            raise ValueError("Maximum speed must be greater than zero.")
        if start_speed_mm_s <= 0:
            raise ValueError("Starting speed must be greater than zero.")
        if start_speed_mm_s > max_speed_mm_s:
            raise ValueError("Starting speed cannot exceed maximum speed.")
        if not 0 <= accel_time_ms <= 1000:
            raise ValueError("Acceleration time must be between 0 and 1000 ms.")
        self._start_speed_mm_s = float(start_speed_mm_s)
        self._max_speed_mm_s = float(max_speed_mm_s)
        self._accel_time_ms = int(accel_time_ms)

    # -- movement ----------------------------------------------------------------------------------------------
    def move_relative_pulses(self, pulses, wait=True):
        del wait
        self._require_connection()
        if pulses == 0:
            return
        self._stopped = False
        self._check_pulses(self._position_pulses + int(pulses))
        self._position_pulses += int(pulses)

    def move_relative_mm(self, distance_mm, wait=True):
        self.move_relative_pulses(self.mm_to_pulses(distance_mm), wait=wait)

    def move_absolute_pulses(self, pulses, wait=True):
        del wait
        self._require_connection()
        self._stopped = False
        self._check_pulses(int(pulses))
        self._position_pulses = int(pulses)

    def move_absolute_mm(self, position_mm, wait=True):
        self.move_absolute_pulses(self.mm_to_pulses(position_mm), wait=wait)

    def home(self, direction="-", wait=True):
        del wait
        self._require_connection()
        if direction not in ("+", "-"):
            raise ValueError("direction must be '+' or '-'")
        self._stopped = False
        self._position_pulses = self._min_pulses if direction == "-" else self._max_pulses

    def stop(self):
        self._require_connection()
        self._stopped = True
        self._busy = False
