"""Fake backend of the Franka Hand driver: an in-memory stand-in for FrankaHandPhysics.

Gate G7: every public member defined here is a method of
``franka_sim.gripper.physics:FrankaHandPhysics`` at the pinned commit
d893e17dc77a338a92a1673a8e616c8b251cc5a9, with the upstream parameter names.
The hand starts fully open, as the kinematic upstream backend does
(backend.py:151), and every command finishes as soon as it is called: no
physics, no motion over time and no blocking.

The real backend's numbers are the device's; the values below are test data
and are marked ``# placeholder``.  The fake can put a rigid object of
``object_width`` metres between the fingers, the same idea as the upstream
``--gripper-object-width`` flag (docs/install.md:139), so a test can exercise a
successful grasp.  With no object the fingers close to 0 m and a grasp of a
non-zero width answers false (docs/robot-state.md:209-211).
"""

from dataclasses import dataclass


@dataclass
class _HandState:
    """The four fields of the upstream ``GripperStateData`` used by the driver."""

    width: float
    max_width: float
    is_grasped: bool
    temperature: int


class FakeFrankaHandPhysics:
    def __init__(self, physics_sim=None, max_width=0.08, temperature=30, settle_timeout=4.0,
                 settle_velocity=1e-3, poll_dt=0.01, stall_polls=3, object_width=None):
        self.max_width = max_width                          # placeholder (upstream device bound is 0.08 m)
        self.temperature = temperature                      # placeholder (upstream stub is 30 Cel)
        self.settle_timeout = settle_timeout                # placeholder (upstream default)
        self.settle_velocity = settle_velocity              # placeholder (upstream default)
        self.poll_dt = poll_dt                              # placeholder (upstream default)
        self.stall_polls = stall_polls                      # placeholder (upstream default)
        self.object_width = object_width                    # placeholder: None means an empty hand
        self.width = max_width                              # placeholder: start fully open
        self.is_grasped = False
        self.is_stuck = False
        self._calls = []

    def _validate(self, width):
        if not 0.0 <= width <= self.max_width:
            raise ValueError(f"width {width} m is outside the 0..{self.max_width} m stroke")

    def homing(self):
        self._calls.append(("homing", {}))
        self.width = self.max_width
        self.is_grasped = False
        self.is_stuck = False
        return True

    def move(self, width, speed):
        self._validate(width)
        self._calls.append(("move", {"width": width, "speed": speed}))
        if self.object_width is not None and self.object_width <= self.width and width < self.object_width:
            self.width = self.object_width
        else:
            self.width = width
        self.is_grasped = False
        self.is_stuck = False
        return True

    def grasp(self, width, epsilon_inner, epsilon_outer, speed, force):
        self._validate(width)
        self._calls.append(("grasp", {"width": width, "epsilon_inner": epsilon_inner,
                                      "epsilon_outer": epsilon_outer, "speed": speed, "force": force}))
        final = 0.0                                         # placeholder: free space closes on nothing
        if self.object_width is not None and self.object_width <= self.width:
            final = self.object_width
        self.width = final
        self.is_grasped = bool(width - epsilon_inner < final < width + epsilon_outer)
        self.is_stuck = False
        return self.is_grasped

    def stop(self):
        self._calls.append(("stop", {}))
        self.width = self.max_width
        self.is_grasped = False
        self.is_stuck = False
        return True

    def get_state(self):
        return _HandState(self.width, self.max_width, self.is_grasped, self.temperature)
