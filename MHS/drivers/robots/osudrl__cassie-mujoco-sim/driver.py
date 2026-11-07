"""OpenMHS driver for gh.osudrl/cassie-mujoco-sim: the Cassie MuJoCo simulation (a direct Driver).

The card names the family-config helper ``MujocoDriver``, but the upstream entry symbol is the ctypes class
``CassieSim`` (example/cassiemujoco.py:31), not the ``mujoco`` Python module: the clone ships a C library over
MuJoCo 2.10 and a Python wrapper, and the ``mujoco`` package is not installed by the card's empty ``install``
block.  A ``MujocoDriver`` would load the MJCF itself through the missing ``mujoco`` module and could not name
``CassieSim`` as ``native`` (the card's entry symbol is an override).  This package is therefore a decorated
``Driver`` over ``CassieSim`` with a package fake; the switch is recorded as a DEVIATION FROM THE CARD in
``RESULT.json``.

The driver exposes the simulator as a ``world.sim`` resource:

* ``cap.world.step.v1`` advances the model by ``ticks`` calls of ``CassieSim.step_pd``.  The action is the ten
  MuJoCo actuator controls ``{ctrl: [10 numbers]}`` in the model's motor-side unit; the driver turns each one into
  the output-side feedforward torque by multiplying it with the model's actuator gear, so that ``cassie_motor_data``
  (src/cassiemujoco.c:641-658) divides it by that gear again and writes exactly the requested control value.
* ``cap.world.reset.v1`` calls ``CassieSim.full_reset`` and writes the simulator time back to zero.  ``full_reset``
  restores the model data, clears the torque delay and reinitializes the state estimator (src/cassiemujoco.c:2008-2032).
* reads: simulated time, ``qpos``, ``qvel``, the actuator ``ctrl``, the tick count, the model timestep and the last
  reset seed.

The limits of ``action.ctrl`` are the ten ``actuator_ctrlrange`` values of ``model/cassie.xml:258-267``; they are
motor-side bounds, and no other numeric bound is declared because no text of the clone states one.  The device is
simulated (R0): there is no hardware backend, no e-stop path to a machine and no operator-required bound.

Every Fact cites a line of the clone at commit 188d3d7f04f0c4ed12db66bdec67884e1c0eb743.  This package is
model-authored and unreviewed: it is checked on the fake backend only (see fake.py and facts.md).
"""

from mhs import canonical
from mhs.driver import Driver, Fact, Field, Limit, action, read

#: The simulator state dimensions of the Cassie model: qpos has 35 entries, qvel 32 and ctrl one per motor.
#: include/cassiemujoco.h:110-190 lists the qpos/qvel entries and the control pointer.
NQ, NV, NU = 35, 32, 10

#: Motor order of the model and of pd_in_t: left hip roll, yaw, pitch, knee, foot, then the right leg
#: (src/cassiemujoco.c:224-234; model/cassie.xml:258-267).
CTRL_NAMES = (
    "left_hip_roll", "left_hip_yaw", "left_hip_pitch", "left_knee", "left_foot",
    "right_hip_roll", "right_hip_yaw", "right_hip_pitch", "right_knee", "right_foot",
)
#: model/cassie.xml:258-267: gear and ctrlrange of the ten actuators, in the motor order above.
GEARS = (25.0, 25.0, 16.0, 16.0, 50.0, 25.0, 25.0, 16.0, 16.0, 50.0)
CTRL_MIN = (-4.5, -4.5, -12.2, -12.2, -0.9, -4.5, -4.5, -12.2, -12.2, -0.9)
CTRL_MAX = (4.5, 4.5, 12.2, 12.2, 0.9, 4.5, 4.5, 12.2, 12.2, 0.9)


#: The pd_in_t layout that CassieSim.step_pd expects (include/pd_in_t.h:24-45): only the feedforward torque is
#: used here, so the PD targets and gains stay zero.
class _MotorPd:
    __slots__ = ("torque", "pTarget", "dTarget", "pGain", "dGain")

    def __init__(self):
        self.torque = [0.0] * 5
        self.pTarget = [0.0] * 5
        self.dTarget = [0.0] * 5
        self.pGain = [0.0] * 5
        self.dGain = [0.0] * 5


class _TaskPd:
    __slots__ = ("torque", "pTarget", "dTarget", "pGain", "dGain")

    def __init__(self):
        self.torque = [0.0] * 6
        self.pTarget = [0.0] * 6
        self.dTarget = [0.0] * 6
        self.pGain = [0.0] * 6
        self.dGain = [0.0] * 6


class _LegPd:
    __slots__ = ("taskPd", "motorPd")

    def __init__(self):
        self.taskPd = _TaskPd()
        self.motorPd = _MotorPd()


class _PdInput:
    """A stand-in for the ``pd_in_t`` structure (include/pd_in_t.h:24-45); the native call copies it."""

    __slots__ = ("leftLeg", "rightLeg", "telemetry")

    def __init__(self):
        self.leftLeg = _LegPd()
        self.rightLeg = _LegPd()
        self.telemetry = [0.0] * 9


def _pd_input(ctrl):
    """Build the pd_in_t feedforward torques from the motor-side control values.

    ``cassie_motor_data`` writes ``ctrl = torque / gear`` clamped to the actuator ctrlrange
    (src/cassiemujoco.c:641-658), so the output-side torque that reproduces the requested control is
    ``ctrl * gear``.  Without an action every torque is zero.
    """
    pd = _PdInput()
    if ctrl:
        for index, value in enumerate(ctrl):
            leg = pd.leftLeg if index < 5 else pd.rightLeg
            leg.motorPd.torque[index % 5] = float(value) * GEARS[index]
    return pd


class CassieMujocoSim(Driver):
    device_id = "cassie-sim"
    device_kind = "world.sim"
    resource_id = "world"
    resource_title = "Cassie MuJoCo world"
    mode = "simulated"
    risk = "R0"
    native = "cassiemujoco:CassieSim"
    backends = {"fake": ".fake:FakeCassieSim"}
    display_name = "Cassie MuJoCo simulation"
    vendor, model = "Agility Robotics (Dynamic Robotics Laboratory)", "Cassie"
    tags = ["cassie", "mujoco", "robot", "simulation", "biped", "world"]
    safe_state = ("the simulation stops advancing: after an e-stop no step or reset is accepted until the safety "
                  "reset clears the latch, and the model state stays readable")
    facts = [
        Fact("The repository is a simulation library for Agility Robotics' Cassie robot using MuJoCo",
             source="vendor_doc", ref="README.md:3"),
        Fact("CassieSim.step_pd calls cassie_sim_step_pd", source="upstream_code",
             ref="example/cassiemujoco.py:69-72"),
        Fact("cassie_sim_step_pd simulates one step of the Cassie simulator with PD input and state estimator "
             "output", source="upstream_code", ref="include/cassiemujoco.h:92-95"),
        Fact("The model timestep is 0.0005 s because the controller runs at 2 kHz", source="upstream_code",
             ref="model/cassie.xml:5-6"),
        Fact("The ten actuators are the two legs' hip roll, hip yaw, hip pitch, knee and foot motors, with gear "
             "ratios 25, 25, 16, 16 and 50 and ctrlrange +-4.5, +-4.5, +-12.2, +-12.2 and +-0.9 in the motor "
             "order", source="upstream_code", ref="model/cassie.xml:258-267"),
        Fact("motor() computes the motor-side torque as the output-side torque divided by the actuator gear, "
             "clamps it to actuator_ctrlrange and writes data.ctrl", source="upstream_code",
             ref="src/cassiemujoco.c:641-658"),
        Fact("cassie_sim_full_reset copies a 35-element initial qpos and zeroes qvel, ctrl, qfrc_applied, "
             "xfrc_applied and qacc, clears the torque delay and reinitializes the state estimator; it does not "
             "write the simulator time", source="upstream_code", ref="src/cassiemujoco.c:2008-2032"),
        Fact("CassieSim.set_time writes the simulator time", source="upstream_code",
             ref="example/cassiemujoco.py:144-146"),
        Fact("The state read-back methods take a slice of the MuJoCo data: qpos is the first nq entries, qvel the "
             "first nv entries and ctrl the first nu entries", source="upstream_code",
             ref="example/cassiemujoco.py:104-134"),
    ]
    #: The model as deployed: MuJoCo rigid-body dynamics with contacts and PD-driven motors.  The fake is a
    #: placeholder stand-in, so the contract is honest about what it does not model (spec 05-fidelity FID-002).
    fidelity = {
        "engine": "mujoco",
        "fidelity_level": "F1",
        "determinism": {
            "kind": "none",
            "seed_control": "none",
            "notes": "MuJoCo is deterministic given the full data state, but CassieSim exposes no full snapshot "
                     "and full_reset does not clear MuJoCo's warm-start accelerations, so the driver does not "
                     "claim replay equality; cap.world.reset.v1 records the supplied seed as a label only",
        },
        "timestep_ms": 0.5,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "partial",
        "snapshot_restore": False,
        "gaps": [
            "the fake backend is a kinematic stand-in, not MuJoCo: no contacts, gravity, torque-speed limit, "
            "state estimator or sensor model; it integrates a placeholder motor response only",
            "full_reset restores the model data, the torque delay and the estimator, but not MuJoCo's warm-start "
            "accelerations and not the simulator time; the driver sets the time to zero, so a reset is partial",
            "no physical Cassie is modelled or validated; the UDP interface to a real robot is not bound",
            "the fake's qpos/qvel are the model's array sizes but its inertia and step response are placeholder "
            "test data, not the model's dynamics",
            "only the feedforward motor torque is exposed; the pd_in_t task-level and per-motor target and gain "
            "inputs are not bound",
        ],
    }

    # -- reads ----------------------------------------------------------------------------------------------------
    @read("time_ms", type="integer", unit="ms", description="Simulated time since the last reset")
    def time_ms(self):
        return int(round(float(self.native.time()) * 1000.0))

    @read("qpos", type="array", items="number", length=NQ,
          description="Joint positions (qpos) of the 35-element Cassie model")
    def qpos(self):
        return [float(value) for value in self.native.qpos()]

    @read("qvel", type="array", items="number", length=NV,
          description="Joint velocities (qvel) of the 32-element Cassie model")
    def qvel(self):
        return [float(value) for value in self.native.qvel()]

    @read("ctrl", type="array", items="number", length=NU, unit="1",
          description="Motor-side actuator control values last written to the model")
    def ctrl(self):
        return [float(value) for value in self.native.ctrl()]

    @read("tick", type="integer", unit="1", description="Number of step_pd calls since the last reset")
    def tick(self):
        return int(getattr(self, "_tick", 0))

    @read("timestep_ms", type="number", unit="ms", description="Integration step of the MuJoCo model")
    def timestep_ms(self):
        return float(self.native.timestep()) * 1000.0

    @read("seed", type="integer", unit="1", description="Seed recorded by the last reset (a label only)")
    def seed(self):
        return int(getattr(self, "_seed", 0))

    # -- actions --------------------------------------------------------------------------------------------------
    @action(
        cap="cap.world.step.v1",
        description="Advance the Cassie simulation by ticks step_pd calls with a motor-side control vector",
        input={
            "ticks": Field("integer", unit="1",
                           description="Number of 0.5 ms step_pd calls to run (the catalogue bounds it to 1..10000)"),
            "action": Field(
                "object",
                description="The control applied at every tick; an omitted action steps with zero torque",
                properties={
                    "ctrl": Field(
                        "array", unit="1", length=NU,
                        items=Field("number", description="Motor-side actuator control value"),
                        description="Ten actuator control values in the model's motor order",
                        limit=Limit(min=list(CTRL_MIN), max=list(CTRL_MAX), names=list(CTRL_NAMES), unit="1",
                                    source="upstream_code", ref="model/cassie.xml:258-267",
                                    reason="actuator_ctrlrange of the ten Cassie motors"),
                    ),
                },
            ),
        },
    )
    def step(self, ticks=1, action=None):
        control = action.get("ctrl") if isinstance(action, dict) else None
        pd = _pd_input(control)
        count = int(ticks)
        for _ in range(count):
            self.native.step_pd(pd)
        self._tick = getattr(self, "_tick", 0) + count
        observation = self._observation()
        return {"observation": observation, "tick": self._tick,
                "state_hash": canonical.digest({"observation": observation, "tick": self._tick})}

    @action(
        cap="cap.world.reset.v1",
        description="Restore the model's initial integration state and set the simulator time to zero",
        input={
            "seed": Field("integer", unit="1",
                          description="Seed recorded in the receipt; the model has no random source"),
        },
    )
    def reset_simulation(self, seed=0):
        self.native.full_reset()
        self.native.set_time(0.0)
        self._tick = 0
        self._seed = int(seed)
        return {"observation": self._observation(), "seed": self._seed}

    # -- helpers --------------------------------------------------------------------------------------------------
    def _observation(self):
        return {
            "time": float(self.native.time()),
            "qpos": [float(value) for value in self.native.qpos()],
            "qvel": [float(value) for value in self.native.qvel()],
        }
