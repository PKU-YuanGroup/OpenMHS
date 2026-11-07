"""Fake backend of the pyapt driver: an in-memory stand-in for pyAPT.controller:Controller.

Gate G7: every public method defined here exists on pyAPT.controller:Controller, and the one other attribute the
driver reaches, ``soft_limits``, is assigned by the upstream __init__ (pyAPT/controller.py:76).  The upstream class
opens an FTDI device and speaks binary APT messages; this stand-in keeps the position, velocity and flags in memory
and never imports the clone or talks to hardware.  The starting values and the wide software range are test data,
not facts about any stage, and each is marked placeholder.  The stand-in does not model motion kinematics, the USB
framing, the controller's range check or its status bits beyond the values the driver reads.
"""


class _FakeStatus:
    """The part of pyAPT.controller.ControllerStatus that the driver reads."""

    def __init__(self, controller):
        self.channel = 1
        self.position = controller._position
        self.velocity = controller._velocity
        self.statusbits = controller._status_bits()
        self.position_apt = 0
        self.velocity_apt = 0

    @property
    def forward_hardware_limit_switch_active(self):
        return bool(self.statusbits & 0x01)

    @property
    def reverse_hardware_limit_switch_active(self):
        return bool(self.statusbits & 0x02)

    @property
    def moving(self):
        return bool(self.statusbits & 0x30)

    @property
    def homed(self):
        return bool(self.statusbits & 0x400)

    @property
    def shortstatus(self):
        def add(flag, letter):
            return letter if flag else "-"

        return (f"{add(self.homed, 'H')} {add(self.statusbits & 0x10, 'M')}-{add(self.statusbits & 0x2000, 'S')} "
                f"{add(self.statusbits & 0x01, 'F')}{add(self.statusbits & 0x02, 'R')}"
                f"{add(self.statusbits & 0x4000, 'E')}")


class FakePyapt:
    def __init__(self, **_options):
        self.serial_number = "fake"             # placeholder
        self.label = None                       # placeholder
        self.soft_limits = True                 # placeholder: same initial value as the upstream __init__
        self.max_velocity = 1.0                 # placeholder: the software cap of this stand-in
        self.max_acceleration = 1.0             # placeholder: the software cap of this stand-in
        self._position = 1.0                    # placeholder: starting position in stage units
        self._velocity = 0.0                    # placeholder: stage units per second
        self._minimum_velocity = 0.0            # placeholder
        self._acceleration = 0.1                # placeholder: stage units per second squared
        self._maximum_velocity = 0.2            # placeholder: stage units per second
        self._homed = False                     # placeholder
        self._moving = False                    # placeholder
        self._forward_limit = False             # placeholder
        self._reverse_limit = False             # placeholder
        self._closed = False                    # placeholder
        self._stop_count = 0                    # placeholder
        self._wide_range = (-1.0e9, 1.0e9)      # placeholder: the stand-in adds no travel bound of its own

    # -- reads ---------------------------------------------------------------------------------------------
    def position(self, channel=1, raw=False):
        return self._position

    def status(self, channel=1):
        return _FakeStatus(self)

    def velocity_parameters(self, channel=1, raw=False):
        return (self._minimum_velocity, self._acceleration, self._maximum_velocity)

    # -- writes and actions ---------------------------------------------------------------------------------
    def goto(self, abs_pos_mm, channel=1, wait=True):
        low, high = self._wide_range
        if self.soft_limits and not low <= float(abs_pos_mm) <= high:
            raise ValueError("target outside the stand-in range")
        self._position = float(abs_pos_mm)
        self._velocity = 0.0
        self._moving = False
        if wait:
            return self.status()
        return None

    def move(self, dist_mm, channel=1, wait=True):
        return self.goto(self.position() + float(dist_mm), channel=channel, wait=wait)

    def home(self, wait=True, velocity=None, offset=0):
        self._position = 0.0                    # placeholder: home position of the stand-in
        self._velocity = 0.0
        self._moving = False
        self._homed = True
        if wait:
            return self.status()
        return None

    def set_soft_limits(self, soft_limits):
        self.soft_limits = bool(soft_limits)

    def set_velocity_parameters(self, acceleration=None, max_velocity=None, channel=1):
        if acceleration is None:
            acceleration = self.max_acceleration
        if max_velocity is None:
            max_velocity = self.max_velocity
        self._acceleration = float(min(float(acceleration), self.max_acceleration))
        self._maximum_velocity = float(min(float(max_velocity), self.max_velocity))

    def stop(self, channel=1, immediate=False, wait=True):
        self._stop_count += 1
        self._velocity = 0.0
        self._moving = False
        if wait:
            return self.status()
        return None

    def close(self):
        self._closed = True
        self._moving = False

    # -- internal -------------------------------------------------------------------------------------------
    def _status_bits(self):
        bits = 0
        if self._homed:
            bits |= 0x400
        if self._moving:
            bits |= 0x10
        if self._forward_limit:
            bits |= 0x01
        if self._reverse_limit:
            bits |= 0x02
        return bits
