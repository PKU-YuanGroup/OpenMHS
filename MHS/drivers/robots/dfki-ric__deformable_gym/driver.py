"""OpenMHS driver for gh.dfki-ric/deformable_gym: the FloatingMiaGraspInsole-v0 Gymnasium environment.

A GymnasiumDriver is configuration only: ``env_id`` names the registered environment and the bridge derives the
whole contract from the environment's spaces.  ``cap.world.step.v1`` takes ``{ticks, action}`` where the action is
a 10-value Box (``{"values": [...]}``: 3 end-effector position offsets, 4 orientation offsets and 3 finger
commands), ``cap.world.reset.v1`` takes ``{seed, options}`` and ``cap.world.seed.v1`` ``{seed}``.  The device is
simulated (R0): there is no hardware backend, no e-stop path to a machine and no operator-required limit.

The fake backend is the package's own pure Python environment (``fake.py``), because the upstream package needs
PyBullet, a deformable-body simulation and numpy, and package code never imports or runs the clone.  A backend name
that ``backends`` does not list (``sim``) is served by ``gymnasium.make(env_id)`` (GymnasiumDriver.open_native);
that path needs the upstream package installed and was not run here (README.md).

The ``fidelity`` attribute is the fidelity contract of the model as deployed.  Every constant and rule cites a line
of the clone at the pinned commit (5b67bc9eb28f3c4356c49d0192906fec1752d1a1).  This package is model-authored and
unreviewed: it is checked on the fake backend only.
"""

from mhs.driver import Fact, GymnasiumDriver

INIT = "deformable_gym/__init__.py"
ENV = "deformable_gym/envs/floating_mia_grasp_env.py"
BASE = "deformable_gym/envs/base_env.py"
GRASP = "deformable_gym/envs/grasp_env.py"
MIA = "deformable_gym/robots/mia_hand.py"
URDF = "deformable_gym/assets/robots/urdf/mia_hand.urdf"


class FloatingMiaGrasp(GymnasiumDriver):
    device_id = "floating_mia_grasp"
    env_id = "FloatingMiaGraspInsole-v0"
    native = "deformable_gym.envs.floating_mia_grasp_env:FloatingMiaGraspEnv"
    backends = {"fake": ".fake:FakeFloatingMiaGraspEnv"}
    display_name = "deformable_gym FloatingMiaGraspInsole-v0 (PyBullet simulation)"
    vendor, model = "DFKI RIC", "FloatingMiaGraspInsole-v0"
    tags = ["grasping", "deformable-object", "reinforcement-learning", "simulation", "pybullet", "gymnasium"]
    facts = [
        Fact("The package registers FloatingMiaGraspInsole-v0 with entry point "
             "deformable_gym.envs.floating_mia_grasp_env:FloatingMiaGraspEnv, object_name "
             "'insole_on_conveyor_belt/back' and observable_object_pos True", source="upstream_code",
             ref=f"{INIT}:6-14"),
        Fact("The documented example creates the environment with gymnasium.make('FloatingMiaGraspInsole-v0')",
             source="vendor_doc", ref="README.md:78"),
        Fact("The floating Mia action space bounds the 3 end-effector position offsets by +-0.0005 and the 4 "
             "orientation offsets by +-0.000005", source="upstream_code", ref=f"{ENV}:65-66"),
        Fact("The action space has 10 values: 3 position offsets, 4 orientation offsets and 3 finger commands",
             source="upstream_code", ref=f"{ENV}:117-134"),
        Fact("The finger bounds of the action space are selected from the motor array with actuated_finger_ids "
             "[0, 1, 5]", source="upstream_code", ref=f"{ENV}:88-89"),
        Fact("The observation is the end-effector pose (7 values), 3 finger joint positions and 6 force readings; "
             "with observable_object_pos it appends 3 object position values", source="upstream_code",
             ref=f"{ENV}:162-174"),
        Fact("The observation space bounds the position by -2..2 (z 0..2), the quaternion by -1..1, the three "
             "finger positions by the motor limits, the six forces by -10..10 and the object position by -2..2",
             source="upstream_code", ref=f"{ENV}:91-115"),
        Fact("The default horizon is 100 environment steps", source="upstream_code", ref=f"{BASE}:45"),
        Fact("BaseBulletEnv.step terminates the episode when step_counter reaches the horizon", source="upstream_code",
             ref=f"{BASE}:171"),
        Fact("The simulation registers a time_step subsystem at 100 Hz, with a default time_delta of 0.001 s",
             source="upstream_code", ref=f"{BASE}:48-72"),
        Fact("BaseBulletEnv.reset accepts an options mapping with a hard_reset key that reloads the simulation",
             source="upstream_code", ref=f"{BASE}:104-105"),
        Fact("BaseBulletEnv.reset passes seed and options to gymnasium's Env.reset through "
             "super().reset(seed=seed, options=options)", source="upstream_code", ref=f"{BASE}:97-102"),
        Fact("The reward is 0.0 until the episode terminates; on termination it is +1.0 when the released "
             "object's height is at least 0.9 and -1.0 otherwise", source="upstream_code", ref=f"{GRASP}:60-79"),
        Fact("The initial hand pose is position (0.03, -0.025, 1.0) with Euler angles (-pi/8, pi, 0) converted "
             "by pybullet.getQuaternionFromEuler", source="upstream_code", ref=f"{ENV}:37-39"),
        Fact("MiaHand._correct_index_limit sets the index finger's lower limit to 0.0 and keeps its upper limit",
             source="upstream_code", ref=f"{MIA}:34-37"),
        Fact("The j_index_fle URDF limit is -1.399999976 to 1.399999976", source="upstream_code",
             ref=f"{URDF}:312"),
        Fact("The j_little_fle URDF limit is 0 to 1.396260023", source="upstream_code", ref=f"{URDF}:326"),
        Fact("The j_thumb_opp URDF limit is -0.628 to 0.0", source="upstream_code", ref=f"{URDF}:371"),
        Fact("MiaHand.get_sensor_readings returns six force values", source="upstream_code", ref=f"{MIA}:91-102"),
    ]
    safe_state = ("the simulation stops advancing: no step or reset is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the environment state is kept and stays readable")
    #: The fidelity contract of the model as deployed.  The bridge derives the engine, the determinism kind and
    #: the lockstep clock; they are written out so the whole contract reads in one place.
    fidelity = {
        "engine": "gymnasium:FloatingMiaGraspInsole-v0",
        "fidelity_level": "F1",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "reset(seed) and cap.world.seed.v1 are passed to the environment reset; the upstream "
                     "environment has a fixed initial hand pose, so this fake's state is deterministic, but its "
                     "trajectories are not the upstream PyBullet trajectories and no seed makes them so",
        },
        "timestep_ms": 10.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "scripted stand-in for a PyBullet soft-body grasping task: no contacts, deformation, friction, "
            "actuator, sensor or noise model; finger positions are copied from the command, forces stay zero and "
            "the object does not move",
            "the fake's terminal reward is a placeholder; the upstream reward releases the object, advances the "
            "deformable simulation and tests the object mesh height (deformable_gym/envs/grasp_env.py:60-79)",
            "the published action bounds select motor-array entries 0, 1 and 5 while the commands are applied to "
            "the actuated real joints (index, mrl, thumb); the fake keeps the published bounds and does not model "
            "the joint mapping",
            "no wall-clock pacing: realtime_factor 0, ticks advance simulated time by timestep_ms (the 100 Hz "
            "time_step subsystem of deformable_gym/envs/base_env.py:72) only",
            "the fake returns 19-value Python lists; upstream returns numpy float64 observation arrays and has a "
            "render_mode with a PyBullet GUI",
            "the fake was never compared with a run of the upstream environment; pybullet, numpy and "
            "pytransform3d are not needed by the gate and were not installed",
            "snapshot and restore are not offered: the environment exposes no get_state or set_state",
            "no physical device is modelled and the model was never validated against one",
        ],
    }
