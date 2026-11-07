"""OpenMHS driver for gh.fmdazhar/mujoco_sim: the ur5ePegInHoleGymEnv_easy-v0 Gymnasium environment.

The clone is a UR5e arm and Robotiq Hand-e gripper simulator written in MuJoCo (README.md:3-4).  It registers
six Gymnasium environments; this package targets ``ur5ePegInHoleGymEnv_easy-v0`` because that is the first
registered variant and the one the clone's own render test makes (mujoco_sim/test/test_gym_env_render.py:11).

A GymnasiumDriver is configuration only.  The bridge derives the whole contract from the environment's
spaces: ``cap.world.step.v1`` takes ``{ticks, action}`` with ``action.values`` bounded by the action space
that ``XYZGripperCloseEnv`` installs (the first three elements of the base seven-element Box, i.e. x, y and z
in [-1, 1]; mujoco_sim/envs/wrappers.py:134-138), ``cap.world.reset.v1`` takes ``{seed, options}`` and
``cap.world.seed.v1`` takes ``{seed}``.  The device is simulated (R0): there is no hardware backend, no e-stop
path to a machine and no operator-required limit.

The gate cannot import the upstream package: it needs MuJoCo 3.2.5, gymnasium 1.0.0, glfw and PyOpenGL, and
package code never imports the clone.  The ``fake`` backend is therefore the package's own pure-Python
stand-in (fake.py).  A backend name that ``backends`` does not list (``sim``) is served by
``gymnasium.make("ur5ePegInHoleGymEnv_easy-v0")`` (GymnasiumDriver.open_native) after ``import mujoco_sim``;
that path was not run here.

The ``fidelity`` attribute is the contract of the model as deployed (spec 05-fidelity): MuJoCo rigid-body
dynamics at a 20 ms control step with a seeded reset, and ``gaps`` naming what this package's fake does not
model.  This package is model-authored and unreviewed: it is checked on the fake backend only, and its
evidence is ``contract_checked``, never an MHS-Device level.
"""

from mhs.driver import Fact, GymnasiumDriver

REGISTRATION = "mujoco_sim/__init__.py"
ENV = "mujoco_sim/envs/ur5e_pick_gym_connector.py"
WRAPPERS = "mujoco_sim/envs/wrappers.py"
CONFIG = "mujoco_sim/config/config.py"
BASE = "mujoco_sim/mujoco_gym_env.py"


class UR5ePegInHole(GymnasiumDriver):
    device_id = "ur5e-peg-in-hole"
    env_id = "ur5ePegInHoleGymEnv_easy-v0"
    native = "mujoco_sim.envs:ur5ePegInHoleGymEnv"
    backends = {"fake": ".fake:FakeUR5ePegInHoleEnv"}
    display_name = "mujoco_sim UR5e peg-in-hole (ur5ePegInHoleGymEnv_easy-v0)"
    vendor, model = "fmdazhar", "mujoco_sim"
    tags = ["ur5e", "peg-in-hole", "mujoco", "manipulation", "reinforcement-learning", "simulation", "gymnasium"]
    facts = [
        Fact("The clone is a UR5e arm and Robotiq Hand-e gripper simulator with a state-based peg-in-hole "
             "Gymnasium environment and custom Gymnasium wrappers",
             source="vendor_doc", ref="README.md:3-4"),
        Fact("ur5ePegInHoleGymEnv_easy-v0 is registered with entry point mujoco_sim.envs:ur5ePegInHoleGymEnv",
             source="upstream_code", ref=f"{REGISTRATION}:10-12"),
        Fact("The easy variant applies XYZGripperCloseEnv, SpacemouseIntervention, CustomObsWrapper and "
             "FlattenObservation", source="upstream_code", ref=f"{REGISTRATION}:13-42"),
        Fact("The easy variant ends with gymnasium's FlattenObservation wrapper",
             source="upstream_code", ref=f"{REGISTRATION}:38-41"),
        Fact("The base action space is a seven-element Box from -1.0 to 1.0",
             source="upstream_code", ref=f"{ENV}:234-236"),
        Fact("XYZGripperCloseEnv narrows the action space to the first three elements (x, y, z) of the base Box",
             source="upstream_code", ref=f"{WRAPPERS}:134-138"),
        Fact("The observation space is a Dict of nine Box members, each bounded by +-1e6",
             source="upstream_code", ref=f"{ENV}:172-206"),
        Fact("The easy variant keeps connector_pose, controller_pose, ur5e/tcp_pose, ur5e/tcp_vel, "
             "ur5e/wrist_force and ur5e/wrist_torque", source="upstream_code", ref=f"{REGISTRATION}:27-36"),
        Fact("CustomObsWrapper rebuilds the state Dict with only the kept keys",
             source="upstream_code", ref=f"{WRAPPERS}:54-62"),
        Fact("controller_pose is a six-element array: the controller position and its orientation",
             source="upstream_code", ref=f"{ENV}:540-542"),
        Fact("control_dt is 0.02 s and physics_dt is 0.002 s",
             source="upstream_code", ref=f"{CONFIG}:13-14"),
        Fact("n_substeps is int(control_dt // physics_dt), so one control step runs ten physics steps",
             source="upstream_code", ref=f"{BASE}:34-36"),
        Fact("_max_episode_steps is 1000.0", source="upstream_code", ref=f"{CONFIG}:15"),
        Fact("step sets truncated once _elapsed_steps reaches _max_episode_steps",
             source="upstream_code", ref=f"{ENV}:471-475"),
        Fact("step returns observation, reward, terminated, truncated and info",
             source="upstream_code", ref=f"{ENV}:476"),
        Fact("reset returns the observation and an empty info dict",
             source="upstream_code", ref=f"{ENV}:391-393"),
        Fact("reset accepts an optional seed argument", source="upstream_code", ref=f"{ENV}:257"),
        Fact("Port randomization draws with np.random.uniform from numpy's global generator, so the reset seed "
             "argument does not seed it", source="upstream_code", ref=f"{ENV}:276-279"),
        Fact("reward_shaping is False and sparse_reward_weights is 0 by default",
             source="upstream_code", ref=f"{CONFIG}:88-92"),
        Fact("The step returns the sparse reward while reward_shaping is False",
             source="upstream_code", ref=f"{ENV}:721-723"),
        Fact("task_complete_tolerance is 0.0025", source="upstream_code", ref=f"{CONFIG}:93"),
        Fact("The task is complete when the connector-to-port distance is below the tolerance",
             source="upstream_code", ref=f"{ENV}:710"),
        Fact("The UR5e home joint position is [-1.907, -1.565, 2.350, -2.355, -1.571, 1.234]",
             source="upstream_code", ref=f"{CONFIG}:40"),
        Fact("The default Cartesian workspace bounds are [0.2, -0.3, 0.0] to [0.6, 0.3, 0.05]",
             source="upstream_code", ref=f"{CONFIG}:41"),
        Fact("The environment declares the render modes human and rgb_array",
             source="upstream_code", ref=f"{ENV}:30-35"),
        Fact("The clone pins mujoco 3.2.5 and gymnasium 1.0.0",
             source="upstream_code", ref="requirements.txt:2-3"),
    ]
    safe_state = ("the simulation stops advancing: after an e-stop the runtime refuses step and reset until "
                  "mhs.safety.reset clears the latch, and the last world state stays readable")
    #: The fidelity contract of the model as deployed (spec 05-fidelity section 2).  The bridge derives the
    #: determinism kind and the lockstep clock; they are written out so the whole contract reads in one place.
    fidelity = {
        "engine": "mujoco:ur5ePegInHoleGymEnv_easy-v0",
        "fidelity_level": "F1",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "the fake seeds Python's random.Random from reset(seed) and is deterministic afterwards, "
                     "so one seed repeats a trajectory of this package; the upstream reset accepts a seed but "
                     "draws the port and controller randomization from numpy's global generator "
                     "(ur5e_pick_gym_connector.py:276-279), so a seed does not fix those draws upstream and the "
                     "two backends do not start from the same state",
        },
        "timestep_ms": 20.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "the deployed model is MuJoCo rigid-body dynamics with contacts (F1), but the fake backend is a "
            "pure-Python kinematic stand-in: it models no rigid-body dynamics, contacts, friction, actuator "
            "forces, sensors or noise, and its start positions and step scale are placeholders",
            "the fake does not model the peg-in-hole task, the reward or task-success termination: it returns "
            "the sparse -1 reward, never terminates for success and only truncates at 1000 steps",
            "the fake uses Python's random.Random for its start noise while the upstream reset accepts a seed "
            "but draws from numpy's global generator, so one seed gives different starting states on the two",
            "the easy variant's SpacemouseIntervention wrapper opens a SpaceMouse or a keyboard at construction "
            "and ur5ePegInHoleGymEnv.__init__ calls glfw and creates a MuJoCo renderer, so the sim backend needs "
            "a display and input devices and was not run here",
            "the observation is the flattened 27-value array of the six kept members; its values are placeholder "
            "test data and were not compared with a MuJoCo run",
            "no wall-clock pacing: realtime_factor 0, ticks advance simulated time by timestep_ms only",
            "snapshot and restore are not offered: the environment exposes get_state but no set_state, and the "
            "bridge requires both",
        ],
    }
