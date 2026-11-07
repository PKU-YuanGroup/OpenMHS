"""Fake backend of the Cassie MuJoCo driver: a pure Python stand-in for ``example.cassiemujoco:CassieSim``.

Why a fake: the upstream Python class is a ctypes wrapper over ``libcassiemujoco.so`` and MuJoCo 2.10; neither is
installed here (the card's ``install`` block is empty) and package code never imports or builds the clone.  This
module reproduces the public methods the driver calls ---- ``step_pd``, ``full_reset``, ``time``, ``timestep``,
``qpos``, ``qvel``, ``ctrl``, ``set_time``, ``set_qpos``, ``set_qvel`` and ``set_ctrl`` ---- with the same signatures
and state sizes.  Gate G7 checks every public member against the AST of ``CassieSim`` in the clone.

What this is not: MuJoCo.  It has no contacts, gravity, mass matrix, torque-speed limit, state estimator or sensor
model.  It only divides the pd_in_t feedforward torque by the actuator gear (the mapping of
src/cassiemujoco.c:641-663), clamps it to the model's ctrlrange, integrates a placeholder motor response and advances
the time by the model timestep.  Every number below is test data, marked ``# placeholder``; none of it is a Fact, a
Limit or a claim about the device.  The model constants (gear, ctrlrange, the initial qpos of
src/cassiemujoco.c:2010-2014) are repeated here only so the fake starts and responds like the real wrapper.

Nothing here talks to a device.
"""

# model/cassie.xml:258-267, motor order of src/cassiemujoco.c:224-234; placeholder test data in this fake.
GEARS = (25.0, 25.0, 16.0, 16.0, 50.0, 25.0, 25.0, 16.0, 16.0, 50.0)  # placeholder
CTRL_MIN = (-4.5, -4.5, -12.2, -12.2, -0.9, -4.5, -4.5, -12.2, -12.2, -0.9)  # placeholder
CTRL_MAX = (4.5, 4.5, 12.2, 12.2, 0.9, 4.5, 4.5, 12.2, 12.2, 0.9)  # placeholder

#: qpos/qvel entries of the ten motors (include/cassiemujoco.h:119-146, 157-182); placeholder test data.
QPOS_INDEX = (7, 8, 9, 14, 20, 21, 22, 23, 28, 34)  # placeholder
QVEL_INDEX = (6, 7, 8, 12, 18, 19, 20, 21, 25, 31)  # placeholder
#: Placeholder motor inertias so a step has an observable effect; not the model's mass matrix.
INERTIA = (0.5, 0.5, 0.5, 0.5, 0.25, 0.5, 0.5, 0.5, 0.5, 0.25)  # placeholder

#: The 35 initial qpos values of cassie_sim_full_reset (src/cassiemujoco.c:2010-2014); placeholder test data.
INITIAL_QPOS = (
    0.0, 0.0, 1.01, 1.0, 0.0, 0.0, 0.0,
    0.0045, 0.0, 0.4973, 0.9785, -0.0164, 0.01787, -0.2049,
    -1.1997, 0.0, 1.4267, 0.0, -1.5244, 1.5244, -1.5968,
    -0.0045, 0.0, 0.4973, 0.9786, 0.00386, -0.01524, -0.2051,
    -1.1997, 0.0, 1.4267, 0.0, -1.5244, 1.5244, -1.5968,
)  # placeholder


class FakeCassieSim:
    """The subset of ``CassieSim`` the driver uses, without MuJoCo."""

    def __init__(self, modelfile=None, terrain=False, perception=False, reinit=False, **_options):
        # The constructor options of CassieSim (example/cassiemujoco.py:32) are accepted and kept, not acted on.
        self.modelfile = modelfile
        self.terrain = bool(terrain)
        self.perception = bool(perception)
        self.reinit = bool(reinit)
        self.nq, self.nv, self.nu = 35, 32, 10  # include/cassiemujoco.h:110-190
        self._timestep = 0.0005  # placeholder: model/cassie.xml:5
        self._time = 0.0
        self.full_reset()
        self._time = 0.0

    # -- the integration surface ---------------------------------------------------------------------------------
    def step_pd(self, u):
        """Apply one pd_in_t step: motor torque / gear -> ctrl, then a placeholder integration."""
        for index in range(self.nu):
            leg = u.leftLeg if index < 5 else u.rightLeg
            torque = float(leg.motorPd.torque[index % 5])
            motor_side = torque / GEARS[index]
            motor_side = max(min(motor_side, CTRL_MAX[index]), CTRL_MIN[index])
            self._ctrl[index] = motor_side
            qv = QVEL_INDEX[index]
            qp = QPOS_INDEX[index]
            self._qvel[qv] += motor_side * self._timestep / INERTIA[index]
            self._qpos[qp] += self._qvel[qv] * self._timestep
        self._time += self._timestep

    def full_reset(self):
        """The model-data reset of cassie_sim_full_reset (src/cassiemujoco.c:2008-2032); the time is not touched."""
        self._qpos = list(INITIAL_QPOS)
        self._qvel = [0.0] * self.nv
        self._ctrl = [0.0] * self.nu

    # -- state read-back (example/cassiemujoco.py:92-161) ---------------------------------------------------------
    def time(self):
        return self._time

    def timestep(self):
        return self._timestep

    def qpos(self):
        return list(self._qpos)

    def qvel(self):
        return list(self._qvel)

    def ctrl(self):
        return list(self._ctrl)

    def set_time(self, time):
        self._time = float(time)

    def set_qpos(self, qpos):
        for index in range(min(len(qpos), self.nq)):
            self._qpos[index] = float(qpos[index])

    def set_qvel(self, qvel):
        for index in range(min(len(qvel), self.nv)):
            self._qvel[index] = float(qvel[index])

    def set_ctrl(self, ctrl):
        for index in range(self.nu):
            self._ctrl[index] = float(ctrl[index])
