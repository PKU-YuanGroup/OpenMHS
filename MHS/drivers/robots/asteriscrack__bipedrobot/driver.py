"""OpenMHS driver for gh.asteriscrack/bipedrobot: the MuJoCoV2-v0 BipedEnvV2 Gymnasium environment.

A GymnasiumDriver is configuration only: ``env_id`` names the registered environment and the bridge derives the
whole contract from the environment's spaces.  ``cap.world.step.v1`` takes ``{ticks, action}`` where ``action`` is
``{values: [...]}``: the V2 action space is ``Box(-1.0, 1.0, shape=(12,))``, so the bridge bounds every one of the
twelve values to [-1, 1] and refuses anything outside it before the environment is stepped.  ``cap.world.reset.v1``
takes ``{seed, options}`` and ``cap.world.seed.v1`` takes ``{seed}``.  The device is simulated (R0): there is no
hardware backend, no e-stop path to a machine and no operator-required limit.

The card's first entry symbol, ``envs.mujoco_env:MujocoEnv``, names a module that does not exist in the clone (the
registration at ``envs/mujoco/__init__.py:5`` is broken), so this package uses the card's second entry symbol,
``envs.mujoco.biped_env_v2:BipedEnvV2``, registered as ``MujocoV2-v0`` at ``envs/mujoco/__init__.py:9-13``.  The
Isaac Lab entry cannot run without Isaac Lab and a GPU, which the gate does not have and the driver never installs.

The gate cannot import the clone's stack (MuJoCo, torch, numpy, gymnasium; ``requirements.txt:1-15``), so the
``fake`` backend is the package's own pure Python stand-in for the environment's Gymnasium surface (fake.py).  A
backend name that ``backends`` does not list (``sim``) is served by ``gymnasium.make(env_id)``
(GymnasiumDriver.open_native); that path needs the upstream package installed and imported so that ``MujocoV2-v0``
is registered, and it was not run here.

The ``fidelity`` attribute is the complete fidelity contract of the model as deployed: engine, level, determinism,
timestep, clock, reset, snapshot and the gaps that say what the fake does not model.  Every constant and rule cites
a line of the clone at the pinned commit (bdaa21ee73c9cfa60a7fe76caf5082fc67329891).  This package is model-authored
and unreviewed: it is checked on the fake backend only.
"""

from mhs.driver import Fact, GymnasiumDriver

ENV = "envs/mujoco/biped_env_v2.py"
BASE = "envs/mujoco/base_env.py"
REGISTER = "envs/mujoco/__init__.py"


class BipedRobot(GymnasiumDriver):
    device_id = "bipedrobot"
    env_id = "MujocoV2-v0"
    native = "envs.mujoco.biped_env_v2:BipedEnvV2"
    backends = {"fake": ".fake:FakeBipedEnvV2"}
    device_kind = "world.sim"
    display_name = "asteriscrack BipedRobot MuJoCo V2 (MujocoV2-v0)"
    vendor, model = "asteriscrack", "BipedRobot V2"
    tags = ["biped", "locomotion", "mujoco", "gymnasium", "reinforcement-learning", "simulation"]
    facts = [
        Fact("BipedEnvV2 is the MuJoCo V2 environment class", source="upstream_code", ref=f"{ENV}:130"),
        Fact("MujocoV2-v0 is registered with entry_point envs.mujoco.biped_env_v2:BipedEnvV2 and "
             "max_episode_steps=1000", source="upstream_code", ref=f"{REGISTER}:9-13"),
        Fact("BaseEnv, the base class of BipedEnvV2, extends gymnasium.Env", source="upstream_code",
             ref=f"{BASE}:8"),
        Fact("BaseEnv loads the MuJoCo model with mujoco.MjModel.from_xml_path", source="upstream_code",
             ref=f"{BASE}:13"),
        Fact("The default V2 model path is envs/assets/robotV2/robot_v2.xml", source="upstream_code",
             ref=f"{ENV}:100-103"),
        Fact("The action space is Box(-1.0, 1.0, shape=(12,)): twelve normalized joint targets",
             source="upstream_code", ref=f"{ENV}:285"),
        Fact("The observation space is a Dict of an actor Box and a critic Box", source="upstream_code",
             ref=f"{ENV}:281-284"),
        Fact("The actor observation has 50 values and the privileged critic observation 60 values",
             source="upstream_code", ref=f"{ENV}:251-252"),
        Fact("The actor observation is lin_acc_b(3), ang_vel_b(3), projected_gravity(3), commands(3), "
             "joint_pos_rel(12), joint_vel(12), prev_actions(12) and gait_phase(2)", source="upstream_code",
             ref=f"{ENV}:3-5"),
        Fact("The critic observation is the 50-value actor observation plus base_lin_vel_b(3), height(1) and "
             "feet_forces(6)", source="upstream_code", ref=f"{ENV}:7-8"),
        Fact("The physics step is 0.005 s at 200 Hz, decimation is 4 and the control step is 0.02 s at 50 Hz",
             source="upstream_code", ref=f"{ENV}:77-79"),
        Fact("reset reseeds numpy's generator when a seed is given and resets the MuJoCo data",
             source="upstream_code", ref=f"{ENV}:692-698"),
        Fact("reset returns the observation and an empty info dict", source="upstream_code",
             ref=f"{ENV}:730"),
        Fact("step clips each action to the [-1, 1] range before applying it", source="upstream_code",
             ref=f"{ENV}:733"),
        Fact("step returns the five-tuple (observation, reward, terminated, False, {}) and never truncates itself",
             source="upstream_code", ref=f"{ENV}:773"),
        Fact("The episode terminates when the torso tilt exceeds 0.784 rad or both feet have been airborne for "
             "more than 1/STEP_DT steps", source="upstream_code", ref=f"{ENV}:654-661"),
        Fact("The environment metadata declares human and rgb_array render modes at 50 fps", source="upstream_code",
             ref=f"{ENV}:133"),
    ]
    safe_state = ("the simulation stops advancing: no step, reset or seed is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the environment state is kept and stays readable")
    #: The fidelity contract of the model as deployed.  The control period is STEP_DT = PHYSICS_DT * DECIMATION =
    #: 0.02 s (envs/mujoco/biped_env_v2.py:77-79); the registered MujocoV2-v0 adds a 1000-step TimeLimit
    #: (envs/mujoco/__init__.py:12).  The bridge derives engine, determinism and clock from the live backend; they
    #: are written out so the whole contract reads in one place.
    fidelity = {
        "engine": "gymnasium:MujocoV2-v0",
        "fidelity_level": "F1",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "reset(seed) reseeds numpy's generator upstream and random.Random in this package's fake; the "
                     "dynamics are deterministic when the same implementation is given the same seed and actions, "
                     "but the two generators produce different trajectories for one seed",
        },
        "timestep_ms": 20.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "the fake backend is a pure Python kinematic stand-in: it does not run MuJoCo, the BAM servo and "
            "backlash model, contacts, friction, the shared reward terms or the 50 Hz decimation loop",
            "the fake draws its start state with Python's random.Random; upstream seeds numpy's generator "
            "(envs/mujoco/biped_env_v2.py:693-694), so one seed gives different trajectories on the two",
            "the fake returns Python lists of placeholder values with the upstream observation lengths (50 actor "
            "values, 60 critic values); upstream returns numpy float32 arrays with the real sensor semantics",
            "no rendering, no get_state/set_state: snapshot_restore is false",
            "the fake applies the registered MujocoV2-v0 1000-step TimeLimit itself; the upstream class's step "
            "never truncates (envs/mujoco/biped_env_v2.py:773)",
            "no physical device is modelled and the model was never validated against one",
        ],
    }
