"""Analytic fake backend for the pinned ``GzStepExample`` ControlWorld interface.

This is not a recording and it replays no captured traffic.  It is a small in-memory stand-in for the one
method the driver calls, ``GzStepExample.step_simulation``.  The fake keeps the request fields the upstream
method writes (``pause``, ``step`` and ``multi_step``) and records the calls so the package tests can see what
reached the "world".  It opens no rclpy node, no ROS graph and no Gazebo world.

Every value below is test data, not a device fact or a bound; the placeholder world name and the failure
switches are marked accordingly.

Model review (2026-11-05): the upstream method never raises for a failed call.  When the ControlWorld future
completes without a result it logs an error and returns None, exactly as on success, and it never reads the
response's success field (gz_step_example.py:44-49).  The failure switches reproduce that: the request is counted
as unanswered, the request fields stay as they were, and the method still returns None (the stand-in used to
raise here, which hid that the driver cannot tell a failed call from a successful one).
"""


class FakeGzStep:
    """In-memory stand-in for ``GzStepExample``: only ``step_simulation`` is a public method."""

    def __init__(self, **_options):
        self.world_name = "default"                 # placeholder, not a deployment fact
        self.pause_request = False
        self.step_request = False
        self.multi_step_request = None
        self.succeeded = False
        self.unanswered = 0                         # placeholder counter of calls the "world" did not answer
        self._calls = []
        self._fail_next = False                     # placeholder negative-path switch
        self._fail_all = False                      # placeholder negative-path switch

    def step_simulation(self, steps=1):
        """Mirror the upstream branch: pause is always set; one step uses step, others multi_step.

        An unanswered call returns None like an answered one, as the upstream method does.
        """
        value = int(steps)
        self._calls.append(("step_simulation", (value,)))
        if self._fail_next or self._fail_all:
            self._fail_next = False
            self.unanswered += 1
            self.succeeded = False
            return None
        if value == 1:
            self.pause_request = True
            self.step_request = True
            self.multi_step_request = None
        else:
            self.pause_request = True
            self.step_request = False
            self.multi_step_request = value
        self.succeeded = True
        return None

    # -- test hooks (not GzStepExample members; never used by the driver) -------------------------------------
    def _called(self, name):
        return [args for call_name, args in self._calls if call_name == name]
