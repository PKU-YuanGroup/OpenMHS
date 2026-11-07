"""Fake backend of the PSI simple positioner: a source-shaped stand-in for PSISimplePositioner.

The upstream class (ophyd_devices/devices/simple_positioner.py:7) is an ophyd Device of four EpicsSignal
Components.  This fake keeps the same public surface: ``user_readback``, ``user_setpoint``, ``velocity`` and
``motor_done_move`` Signal-shaped objects, the ``done_value`` and ``stop_value`` constants, the ``stopped`` flag,
``move()`` and ``stop()``.  It implements no other public method, because gate G7 compares the public methods with
the upstream class.

Model review (2026-11-05): ``stop()`` and ``move()`` follow the pinned upstream for this class.  PSISimplePositioner
declares no ``motor_stop`` Signal and ``override_suffixes`` cannot add one (psi_positioner_base.py:133-146 only warns
for a signal the class does not implement), so ``stop()`` always takes the fallback: it writes the value read from
``user_readback`` into ``user_setpoint`` (psi_positioner_base.py:319-321), sets ``stopped`` and fails the running
move status (psi_device_base.py:158-168, 201-211).  The fake axis then moves to that new setpoint and only its own
motion sets the done flag; the author's fake froze the axis and set the done flag at once, which hid that the
fallback is a new target, not a stop.  ``stopped`` is reset only by ``stage()`` upstream (psi_device_base.py:113),
never by ``move()``; the author's fake reset it on every move.

Nothing here imports ophyd, pyepics or the upstream package, opens a Channel Access connection or reads a PV.  Every
number is a placeholder chosen for the tests, not a fact about an axis: the start position, velocity, the motion
step, the tick interval and the done/stop constants.  The fake moves 0.05 engineering units per 0.01 s tick toward
the current setpoint and therefore reaches a one-unit target after about 0.2 s; it does not complete instantly, so a
stop or e-stop has a running move to interrupt.  A real motor record decelerates and may overshoot the read-back
value before it returns to it; the fake does not model that.
"""

import threading
import time


class _FakeSignal:
    """One Signal-shaped object: ``get`` records the requested freshness; the fake writes the value internally."""

    def __init__(self, value):
        self._value = value
        self._calls = []
        self._lock = threading.Lock()

    def get(self, *, use_monitor=None):
        with self._lock:
            self._calls.append(use_monitor)
            return self._value

    def set(self, value, **kwargs):
        with self._lock:
            self._value = value
        return None

    def put(self, value, wait=True, **kwargs):
        return self.set(value)


class _FakeStatus:
    """The completion object ``move(wait=False)`` returns; only ``done`` and ``success`` are read by the driver."""

    def __init__(self):
        self.done = False
        self.success = False
        self._exception = None

    def set_finished(self):
        if not self.done:
            self.done = True
            self.success = True

    def set_exception(self, exception):
        if not self.done:
            self.done = True
            self.success = False
            self._exception = exception


class FakePSISimplePositioner:
    stop_value = 1  # placeholder (the upstream class also declares 1)
    done_value = 1  # placeholder (the upstream class also declares 1)

    def __init__(self, **_options):
        self.user_readback = _FakeSignal(0.0)       # placeholder start position
        self.user_setpoint = _FakeSignal(0.0)       # placeholder start setpoint
        self.velocity = _FakeSignal(1.0)            # placeholder velocity
        self.motor_done_move = _FakeSignal(1)       # placeholder: 1 means done
        self.stopped = False
        self.move_count = 0
        self.stop_count = 0
        self._position = 0.0                        # placeholder start position
        self._lock = threading.RLock()
        self._thread = None
        self._status = None

    def _setpoint(self):
        with self.user_setpoint._lock:
            return self.user_setpoint._value

    def move(self, position, wait=False, timeout=None, moved_cb=None, **kwargs):
        target = float(position)
        with self._lock:
            if self._status is not None:
                self._status.set_exception(RuntimeError("the fake axis received a new target"))
            self.move_count += 1
            self._status = _FakeStatus()
            # The upstream move() does not touch the stopped flag; only stage() resets it.
            self.user_setpoint.set(target)
            self.motor_done_move.set(0)  # placeholder: 0 means moving
            status = self._status
            if self._thread is None or not self._thread.is_alive():
                self._thread = threading.Thread(target=self._run, daemon=True)
                self._thread.start()
        if wait:
            deadline = time.monotonic() + (timeout if timeout is not None else 10.0)  # placeholder bound
            while not status.done and time.monotonic() < deadline:
                time.sleep(0.01)
        return status

    def _run(self):
        """Drive the fake axis toward the current setpoint; only arrival sets the done flag."""
        step = 0.05       # placeholder engineering units per tick
        tick_s = 0.01     # placeholder tick interval
        while True:
            with self._lock:
                target = self._setpoint()
                position = self._position
                if abs(target - position) <= step:
                    self._position = target
                    self.user_readback.set(target)
                    if self._status is not None:
                        self._status.set_finished()
                        self._status = None
                    self.motor_done_move.set(self.done_value)
                    self._thread = None
                    return
                self._position = position + (step if target > position else -step)
                self.user_readback.set(self._position)
            time.sleep(tick_s)

    def stop(self, *, success=False):
        """The upstream fallback for this class: hold user_setpoint at user_readback.get(), then cancel statuses."""
        with self._lock:
            self.stop_count += 1
            value = self.user_readback.get()
            self.user_setpoint.put(value)
            self.stopped = True
            if self._status is not None:
                self._status.set_exception(RuntimeError("Device has been stopped"))
                self._status = None
