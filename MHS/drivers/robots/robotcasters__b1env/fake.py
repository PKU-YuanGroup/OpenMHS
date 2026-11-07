"""Fake backend of the B1Sim driver: a pure Python kinematic stand-in for ``B1Env.b1_env:B1Sim``.

Why a fake: the upstream module imports numpy, pybullet and gymnasium and builds a pinocchio
``RobotWrapper`` from ``b1_raw.urdf`` (B1Env/b1_env.py:3-16 and :54-55); the gate never installs or imports the clone.
This module mirrors the public surface the Gymnasium bridge uses and that ``B1Sim`` exposes (``reset``, ``step``,
``close``, ``get_state``, ``get_info``, ``send_joint_command``; gate G7).  The joint layout and the action and
observation bounds are those the upstream reads from the same URDF (B1Env/b1_env.py:69-95).  Every numeric constant
below is test data for the stand-in and is marked ``# placeholder``; it is not a fact of the device.

The upstream ``reset`` and ``step`` return only the info dict ``{"q", "dq"}`` (B1Env/b1_env.py:118-121 and
:132-138), which is not the Gymnasium ``(observation, info)`` / five-tuple shape the bridge unpacks.  This fake
therefore converts the same ``q`` and ``dq`` into the 24-element observation the upstream observation space declares
and returns a reward of 0 with terminated and truncated false; the driver's fidelity ``gaps`` disclose that
adaptation.  It is a per-joint kinematic stand-in, not the upstream PyBullet rigid-body model: no contacts,
inertia coupling, gravity, friction or actuator dynamics, and it was never compared with the upstream simulator.

Nothing here talks to a device.
"""

# B1Env/b1_env.py:39 sets the PyBullet time step to 1/240 s; one upstream step advances one such step.
TIMESTEP_S = 1.0 / 240.0                        # placeholder: PyBullet time step in seconds
# B1Env/b1_env.py:113-116 resets 12 active joints to angle 0.0 with velocity 0.0.
JOINT_COUNT = 12                                # placeholder: number of actuated joints
# B1Env/robots/b1_raw.urdf:62,119,176 and the same limits for the other three legs at :259,316,373,
# :456,513,570 and :653,710,767.  The order is FR, FL, HR, HL, each hip/thigh/knee.
JOINT_LOWER = [-0.75, -1.0, -2.6] * 4           # placeholder: URDF jointLowerLimit
JOINT_UPPER = [0.75, 3.5, -0.6] * 4             # placeholder: URDF jointUpperLimit
JOINT_EFFORT = [91.0035, 93.33, 140.0] * 4      # placeholder: URDF effort (action bound)
JOINT_VELOCITY = [19.69, 23.32, 15.55] * 4      # placeholder: URDF velocity (observation bound)
# The upstream dynamics are PyBullet's; this stand-in integrates each joint on its own with a placeholder inertia.
JOINT_INERTIA = 0.1                             # placeholder: per-joint rotor inertia in kg m^2, test data
REWARD = 0.0                                    # placeholder: the upstream step returns no reward


class Box:
    """Duck-typed ``gymnasium.spaces.Box``: the bridge reads ``low``, ``high``, ``shape`` and ``dtype``."""

    def __init__(self, low, high):
        self.low = list(low)
        self.high = list(high)
        self.shape = (len(self.low),)
        self.dtype = "float32"


class FakeB1Sim:
    """B1Sim without pybullet or pinocchio: the same joint methods on a per-joint kinematic model."""

    def __init__(self, render_mode=None, record_path=None, useFixedBase=False):
        # B1Env/b1_env.py:94-95 builds these two Box spaces from the URDF joint limits.
        self.observation_space = Box(JOINT_LOWER + [-value for value in JOINT_VELOCITY],
                                     JOINT_UPPER + list(JOINT_VELOCITY))  # placeholder
        self.action_space = Box([-value for value in JOINT_EFFORT], list(JOINT_EFFORT))  # placeholder
        self.render_mode = render_mode          # placeholder: only names the upstream option
        self.record_path = record_path          # placeholder: only names the upstream option
        self.useFixedBase = useFixedBase        # placeholder: only names the upstream option
        self._q = [0.0] * JOINT_COUNT           # placeholder
        self._dq = [0.0] * JOINT_COUNT          # placeholder
        self._torque = [0.0] * JOINT_COUNT      # placeholder
        self._closed = False

    def reset(self, *, seed=None, options=None):
        """Zero the 12 active joints, like B1Env/b1_env.py:113-116; the upstream reset ignores seed and options.

        The upstream returns only ``{"q", "dq"}`` (:118-121); this fake returns the tuple the Gymnasium bridge
        unpacks, with the 24-element observation the upstream observation space declares.
        """
        self._check_open()
        self._q = [0.0] * JOINT_COUNT          # placeholder: upstream target_joint_angles = 12 * [0.0]
        self._dq = [0.0] * JOINT_COUNT         # placeholder: upstream resets velocity to 0.0
        self._torque = [0.0] * JOINT_COUNT     # placeholder
        q, dq = self.get_state()
        return self._observation(), self.get_info(q, dq)

    def step(self, action):
        """Apply the torque command and advance one 1/240 s kinematic step (upstream :132-138).

        The upstream returns only ``{"q", "dq"}``; this fake returns the five-tuple the bridge unpacks, with the
        same ``q`` and ``dq`` in ``info``.  The per-joint integrator is placeholder test dynamics, not PyBullet.
        """
        self._check_open()
        self.send_joint_command(action)
        for index in range(JOINT_COUNT):
            acceleration = self._torque[index] / JOINT_INERTIA                       # placeholder
            velocity = self._dq[index] + acceleration * TIMESTEP_S                   # placeholder
            velocity = max(-JOINT_VELOCITY[index], min(JOINT_VELOCITY[index], velocity))  # placeholder
            # No position clamp: upstream reset puts every joint at 0.0, which is already above the
            # URDF upper limit -0.6 of the four knees, so the upstream observation Box and its reset
            # state disagree; the fake integrates from the same zero state without adding a rule.
            self._dq[index] = velocity
            self._q[index] = self._q[index] + velocity * TIMESTEP_S                  # placeholder
        q, dq = self.get_state()
        return self._observation(), REWARD, False, False, self.get_info(q, dq)

    def close(self):
        """Stop the stand-in; the upstream disconnects its PyBullet client (B1Env/b1_env.py:158-160)."""
        self._closed = True

    def get_state(self):
        """Return the 12 joint positions and velocities (B1Env/b1_env.py:162-176) as plain lists."""
        return list(self._q), list(self._dq)

    def get_info(self, q, dq):
        """Return ``{"q": q, "dq": dq}`` like B1Env/b1_env.py:150-156."""
        return {"q": q, "dq": dq}

    def send_joint_command(self, tau):
        """Record the commanded torques; the upstream applies them with p.TORQUE_CONTROL (:203-219)."""
        if len(tau) != JOINT_COUNT:
            raise ValueError(f"expected {JOINT_COUNT} joint torques, got {len(tau)}")
        self._torque = [float(value) for value in tau]

    def _observation(self):
        """The upstream observation space concatenates the joint positions and velocities (:89-95)."""
        return list(self._q) + list(self._dq)

    def _check_open(self):
        if self._closed:
            raise RuntimeError("the simulation is closed")
