"""Fake backend of the SmarPod driver: an in-memory stand-in for OphydSmarPod:SmarSignal.

Gate G7: every public method defined here exists on the upstream class ``SmarSignal`` in the clone, except
``stop``.  ``SmarSignal`` itself has no stop method; the stop of the vendor API is the module call
``smarpod.Stop(handle)`` used by the upstream setup (src/SmarPodMain.py:109), and both the real adapter and this fake
expose it as ``stop`` so the driver has one native stop path.  The gate reports that extra name as
``G7.MAYBE_ABSENT`` because the clone names the vendor stop and because the class inherits an external base.

The fake keeps the API of the upstream class: ``get`` returns the six pose components in the order of
``pose_to_double_list`` (src/SmarPodMain.py:45-53); ``set`` checks reachability, moves and returns after the status
is stopped; ``get_status`` reports stopped; ``trigger`` waits for stopped; ``check_pose`` is the reachability check;
``tear_down`` closes it.  Movement takes a short simulated time and can be interrupted by ``stop`` so the fake does
not claim an instantaneous move or an untested stop.

Every value is a placeholder chosen for the tests, not a fact about the SmarPod: the starting pose, the simulated
travel time and the poll interval are test data and are marked ``# placeholder``.  Nothing here imports smaract,
opens a device or talks to hardware.
"""

import math
import time


class _FakeStatus:
    """The small part of ``ophyd.StatusBase`` the upstream and this package observe: done and success."""

    def __init__(self):
        self.done = False
        self.success = False

    def set_finished(self):
        self.done = True
        self.success = True

    def set_exception(self, _error):
        self.done = True
        self.success = False


class FakeSmarSignal:
    def __init__(self, name="hexapod", optional_handle=None, **_options):
        self.name = name
        self.handle = optional_handle if optional_handle is not None else 1  # placeholder
        self.status = None
        self._pose = [0.01, 0.02, 0.03, 0.1, 0.2, 0.3]  # placeholder: the fake's starting pose
        self._moving = False
        self._stop_count = 0
        self._closed = False

    # -- reads ------------------------------------------------------------------------------------------------
    def get(self):
        if self._closed:
            raise RuntimeError("placeholder: the fake SmarPod is closed")
        return list(self._pose)

    def get_status(self):
        return not self._moving

    # -- motion ------------------------------------------------------------------------------------------------
    def check_pose(self, pose):
        try:
            values = [float(item) for item in pose]
        except (TypeError, ValueError):
            return False
        return len(values) == 6 and all(math.isfinite(item) for item in values)

    def set(self, pose):
        values = [float(item) for item in pose]
        if not self.check_pose(values):
            raise ValueError("placeholder: the fake SmarPod rejects this pose as unreachable")
        if self._closed:
            raise RuntimeError("placeholder: the fake SmarPod is closed")
        start = list(self._pose)
        self.status = _FakeStatus()
        self._moving = True
        generation = self._stop_count
        started = time.monotonic()
        duration = 0.05  # placeholder: simulated travel time, not a device fact
        while True:
            if self._stop_count != generation:
                self._moving = False
                self.status.set_finished()
                return
            fraction = min(1.0, (time.monotonic() - started) / duration)
            self._pose = [low + (high - low) * fraction for low, high in zip(start, values)]
            if fraction >= 1.0:
                break
            time.sleep(0.005)  # placeholder: simulation poll interval
        self._pose = values
        self._moving = False
        self.status.set_finished()

    def trigger(self):
        deadline = time.monotonic() + 5.0  # placeholder: bounded wait of the fake, not a device fact
        while self._moving:
            if time.monotonic() >= deadline:
                raise TimeoutError("placeholder: the fake SmarPod did not stop")
            time.sleep(0.005)  # placeholder: simulation poll interval
        return self.status

    def verify_stopped_status(self):
        if not self.get_status():
            raise RuntimeError("placeholder: the fake SmarPod did not stop")

    def verify_reachable_position(self, pose):
        if not self.check_pose(pose):
            raise ValueError("placeholder: the fake SmarPod rejects this pose as unreachable")

    # -- the vendor stop and teardown ----------------------------------------------------------------------------
    def stop(self):
        self._stop_count += 1
        self._moving = False
        if self.status is not None:
            self.status.set_finished()

    def tear_down(self):
        self._closed = True
        self._moving = False
