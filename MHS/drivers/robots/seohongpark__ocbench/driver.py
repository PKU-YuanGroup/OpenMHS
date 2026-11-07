"""OpenMHS driver for gh.seohongpark/ocbench: the ``block-cpu-single-task1-v0`` environment.

OCBench is a controllable robotic manipulation benchmark whose CPU environments follow the Gymnasium
interface and wrap a MuJoCo model (``README.md:55-56``).  This package targets the first registered CPU
environment, ``block-cpu-single-task1-v0``: a UR5e arm with a Robotiq 2F85 gripper moving one cube to a
target (``ocbench/__init__.py:74-79``).  ``ocbench.envs.block_env:BlockEnv`` is the card's AST-confirmed
entry class and the environment's import path, so it is the ``native`` symbol.

A GymnasiumDriver is configuration only.  ``env_id`` names the environment, ``env_kwargs`` selects the
single-cube task, and the bridge derives the whole contract from the environment's spaces:
``cap.world.step.v1`` takes ``{ticks, action}`` with ``action.values`` a seven-value array bounded by the
environment's ``Box(-1, 1)`` (``ocbench/envs/manipulation_env.py:107-114``), ``cap.world.reset.v1`` takes
``{seed, options}`` and ``cap.world.seed.v1`` takes ``{seed}``.  The device is simulated (R0): there is no
hardware backend, no e-stop path to a machine and no operator-required limit.

The gate cannot import the upstream package (it needs MuJoCo, dm_control, Gymnasium and numpy,
``pyproject.toml:9-14``), and package code never imports the clone, so the ``fake`` backend is the
package's own pure Python stand-in (``fake.py``).  A backend name that ``backends`` does not list (``sim``)
is served by ``gymnasium.make(env_id, **env_kwargs)`` through ``GymnasiumDriver.open_native``; that path
needs the upstream package and was not run here.

The ``fidelity`` attribute is the contract of the model as deployed (spec 05-fidelity FID-002): MuJoCo
rigid-body dynamics with contacts (F1), a 20 ms control step, seeded resets, lockstep time and a full reset.
The ``gaps`` name what this package's fake does not model.  For the single-cube task the observation vector
is 28 values: six joint positions, six joint velocities, three scaled effector positions, cos and sin of
the effector yaw, scaled gripper opening, gripper contact, and the cube's three positions, four quaternion
values and cos and sin of its yaw (``manipulation_env.py:374-393`` and ``block_env.py:326-333``).  This
package is model-authored and unreviewed: it is checked on the fake backend only.
"""

from mhs.driver import Fact, GymnasiumDriver

INIT = "ocbench/__init__.py"
BLOCK = "ocbench/envs/block_env.py"
MANIP = "ocbench/envs/manipulation_env.py"
ENV = "ocbench/envs/env.py"


class BlockSingleTask1(GymnasiumDriver):
    device_id = "ocbench-block-single-task1"
    env_id = "block-cpu-single-task1-v0"
    env_kwargs = {"env_type": "single", "task_id": 1}
    native = "ocbench.envs.block_env:BlockEnv"
    backends = {"fake": ".fake:FakeBlockEnv"}
    display_name = "OCBench block-cpu-single-task1-v0 (MuJoCo UR5e cube manipulation)"
    vendor, model = "Seohong Park", "block-cpu-single-task1-v0"
    tags = ["ocbench", "mujoco", "manipulation", "block", "reinforcement-learning", "simulation", "gymnasium"]
    facts = [
        Fact("The README's quick-start example makes block-cpu-single-task1-v0 and steps it with an action "
             "sampled from its action space", source="vendor_doc", ref="README.md:62-70"),
        Fact("block-cpu-single-task1-v0 is registered with entry point ocbench.envs.block_env:BlockEnv, "
             "max_episode_steps=1250 and kwargs env_type='single', task_id=1", source="upstream_code",
             ref=f"{INIT}:74-79"),
        Fact("ocbench.make returns gymnasium.make(env_name, **kwargs) for CPU environments", source="upstream_code",
             ref=f"{INIT}:35-44"),
        Fact("BlockEnv subclasses ManipulationEnv and the single env_type installs one cube", source="upstream_code",
             ref=f"{BLOCK}:9-21"),
        Fact("The single task is named move and its goal position is [0.425, 0.0, 0.03]", source="upstream_code",
             ref=f"{BLOCK}:58-65"),
        Fact("The action space is a Box of seven float32 values from -1 to 1", source="upstream_code",
             ref=f"{MANIP}:107-114"),
        Fact("The per-joint action deltas are 0.18, 0.18, 0.18, 0.36, 0.36, 0.36 and 0.12 times "
             "action_delta_scale", source="upstream_code", ref=f"{MANIP}:79-82"),
        Fact("unnormalize_action clips every action value to [-1, 1] and multiplies it by the joint action "
             "deltas", source="upstream_code", ref=f"{MANIP}:120-122"),
        Fact("ManipulationEnv defaults physics_timestep to 0.002 s and control_timestep to 0.02 s",
             source="upstream_code", ref=f"{MANIP}:13-25"),
        Fact("set_timesteps sets the number of physics steps per control step to control_timestep divided by "
             "physics_timestep", source="upstream_code", ref=f"{ENV}:271-288"),
        Fact("CustomMuJoCoEnv.step applies the action, steps the model nstep times, computes the flags, "
             "observation and reward, and returns the five-tuple", source="upstream_code", ref=f"{ENV}:222-244"),
        Fact("The state observation concatenates joint positions, joint velocities, the scaled effector "
             "position, cos and sin of the effector yaw, the scaled gripper opening and gripper contact",
             source="upstream_code", ref=f"{MANIP}:374-393"),
        Fact("BlockEnv appends every cube's three positions, four quaternion values, cos yaw and sin yaw to "
             "the observation", source="upstream_code", ref=f"{BLOCK}:326-333"),
        Fact("The observation space is a Box from -inf to +inf with the observation shape", source="upstream_code",
             ref=f"{MANIP}:95-105"),
        Fact("The reward is 1.0 when success is true, failure is false and the state is healthy; otherwise 0.0",
             source="upstream_code", ref=f"{MANIP}:395-396"),
        Fact("A cube is successful when its distance to the target mocap is at most 0.04", source="upstream_code",
             ref=f"{BLOCK}:244-255"),
        Fact("The episode terminates when terminate_at_success and success, or failure, or the state is not "
             "healthy", source="upstream_code", ref=f"{MANIP}:409-410"),
        Fact("terminate_at_success defaults to True", source="upstream_code", ref=f"{MANIP}:18"),
        Fact("CustomMuJoCoEnv.truncate_episode returns False, so the environment itself never truncates",
             source="upstream_code", ref=f"{ENV}:118-123"),
        Fact("A reset calls Gymnasium's reset(seed=seed, options=options), initializes the episode and returns "
             "the observation and info", source="upstream_code", ref=f"{ENV}:184-211"),
    ]
    safe_state = ("the simulation stops advancing: no step or reset is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the environment state is kept and stays readable")
    #: The fidelity contract of the model as deployed (spec 05-fidelity section 2).  The bridge derives the
    #: engine, the determinism kind and the lockstep clock; they are written out so the whole contract reads in
    #: one place.
    fidelity = {
        "engine": "mujoco:block-cpu-single-task1-v0",
        "fidelity_level": "F1",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "reset(seed) seeds Gymnasium's generator and the MuJoCo model then advances "
                     "deterministically, so one seed and one action sequence repeat a trajectory; this "
                     "package's fake draws its start state from Python's random.Random, so the same seed gives "
                     "a different trajectory on the fake and upstream",
        },
        "timestep_ms": 20.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "the upstream model is MuJoCo rigid-body dynamics with contacts (F1): the UR5e and Robotiq contacts, "
            "actuator forces, inverse kinematics and the block task are not modelled by the fake, which advances "
            "a simple analytic state instead",
            "the fake does not compute task success, the target tolerance, the reward or termination; it returns "
            "reward 0.0, terminated False and truncates at the registered step limit",
            "the fake draws its start state from Python's random.Random, upstream uses Gymnasium's seeded numpy "
            "generator, so a seed gives different state vectors on the two",
            "the fake returns a flat list of Python floats; upstream returns a numpy concatenation",
            "no wall-clock pacing: realtime_factor 0, ticks advance simulated time by timestep_ms only",
            "snapshot and restore are not offered: the environment exposes no get_state or set_state",
            "no physical device is modelled and the model was never validated against one",
        ],
    }
