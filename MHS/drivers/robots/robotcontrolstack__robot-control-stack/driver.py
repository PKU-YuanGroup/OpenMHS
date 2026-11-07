"""OpenMHS driver for gh.robotcontrolstack/robot-control-stack: the ``rcs/fr3`` Gymnasium environment.

The package serves one environment of the Robot Control Stack family.  ``rcs/fr3`` is registered by the clone as
``EmptyWorldFR3()`` and composes a Franka Research 3 arm with a Franka Hand in an empty MuJoCo world.  A
``GymnasiumDriver`` is configuration only: ``env_id`` selects the environment and the bridge derives
``cap.world.step.v1``, ``cap.world.reset.v1`` and ``cap.world.seed.v1`` from the environment's spaces.  The FR3 config
uses Cartesian TQuat control, so one action is a relative 7-value pose offset plus one gripper value, both nested
under the robot name ``right``.

The device is simulated (R0): there is no hardware backend and no path to a machine.  The gate never imports or
installs the clone; it runs the package's pure Python ``fake`` backend, which stands in for the environment returned
by ``gymnasium.make("rcs/fr3")``.  A backend name that ``backends`` does not list (``sim``) is served by
``gymnasium.make(env_id)`` through ``GymnasiumDriver.open_native``; that path needs the upstream package, MuJoCo and
its compiled extension and was not run here.

The ``fidelity`` attribute is the fidelity contract of the deployed model (spec 05-fidelity FID-002).  The fake is
an event-driven kinematic stand-in, so the contract claims F0 and no fixed timestep; the registered upstream
environment runs MuJoCo and is named in the gaps.  Every fact cites a line of the clone at the pinned commit
afb3795ae9f49f9992bb61518eef6e7277b9011f.  This package is model-authored and unreviewed; it is checked on the fake
backend only.
"""

from mhs.driver import Fact, GymnasiumDriver

CONFIGS = "python/rcs/envs/configs.py"
BASE = "python/rcs/envs/base.py"
SCENES = "python/rcs/envs/scenes.py"


class RcsFr3(GymnasiumDriver):
    device_id = "rcs-fr3"
    env_id = "rcs/fr3"
    native = "rcs.envs.base:SimEnv"
    backends = {"fake": ".fake:FakeFr3Env"}
    display_name = "Robot Control Stack EmptyWorldFR3 (rcs/fr3)"
    vendor, model = "Robot Control Stack", "EmptyWorldFR3 (rcs/fr3)"
    tags = ["robot-arm", "fr3", "franka", "mujoco", "reinforcement-learning", "simulation", "gymnasium"]
    facts = [
        Fact("The rcs/fr3 environment is registered with gymnasium as EmptyWorldFR3()", source="upstream_code",
             ref=f"{CONFIGS}:628"),
        Fact("The FR3 environment controls the arm in Cartesian TQuat mode", source="upstream_code",
             ref=f"{CONFIGS}:86"),
        Fact("The FR3 environment configures SimConfig with realtime=True, async_control=False, frequency=1 Hz and "
             "max_convergence_steps=500", source="upstream_code", ref=f"{CONFIGS}:84"),
        Fact("When async_control is false, SimEnv.step_sim calls sim.step_until_convergence() instead of a fixed "
             "number of physics steps", source="upstream_code", ref=f"{BASE}:267-278"),
        Fact("The FR3 robot is named right (robot_prefix_template)", source="upstream_code", ref=f"{CONFIGS}:35"),
        Fact("MultiRobotWrapper builds the action and observation spaces as dicts keyed by the robot name",
             source="upstream_code", ref=f"{BASE}:462-465"),
        Fact("The environment wraps each robot in RelativeActionSpace unless relative_to is RelativeTo.NONE",
             source="upstream_code", ref=f"{SCENES}:362-365"),
        Fact("A relative Cartesian action defaults to at most 0.5 m of translation (DEFAULT_MAX_CART_MOV)",
             source="upstream_code", ref=f"{BASE}:725"),
        Fact("The relative TQuat action box bounds the three translation elements by +-max_cart_mov, the quaternion "
             "scalar by -1 and 1, and the three quaternion vector elements by -inf and inf", source="upstream_code",
             ref=f"{BASE}:70-79"),
        Fact("The gripper action box is one value from 0 (closed) to 1 (open)", source="upstream_code",
             ref=f"{BASE}:106-108"),
        Fact("TQuatDictType is a tquat field of 7 values bounded by [-0.855, -0.855, -1, -1, -inf, -inf, -inf] and "
             "[0.855, 0.855, 1.188, 1, inf, inf, inf]", source="upstream_code", ref=f"{BASE}:59-67"),
        Fact("JointsDictType bounds the joints array element-wise by the robot's joint limits", source="upstream_code",
             ref=f"{BASE}:82-90"),
        Fact("TRPYDictType is an xyzrpy field of 6 values bounded by [-0.855, -0.855, -1, -180, -180, -180] degrees "
             "and [0.855, 0.855, 1.188, 180, 180, 180] degrees", source="upstream_code", ref=f"{BASE}:34-44"),
        Fact("ArmObsType joins TQuatDictType, JointsDictType and TRPYDictType and adds tquat_flange",
             source="upstream_code", ref=f"{BASE}:170-178"),
        Fact("The gripper wrapper adds one normalized width to the observation", source="upstream_code",
             ref=f"{BASE}:1090-1097"),
        Fact("SimEnv.step advances the simulation and then returns (observation, reward, terminated, truncated, info)",
             source="upstream_code", ref=f"{BASE}:257-265"),
        Fact("CoverWrapper.reset resets the simulator, seeds only the wrapper's np_random, then advances the simulator "
             "30 steps to apply the reset state", source="upstream_code", ref=f"{BASE}:309-322"),
    ]
    safe_state = ("the simulation stops advancing: after an e-stop the runtime refuses step and reset until "
                  "mhs.safety.reset clears the latch, while the last observation stays readable")
    #: Fidelity contract of the deployed model (spec 05-fidelity section 2).  The bridge derives the engine,
    #: determinism kind and lockstep clock from the environment; they are written out so the contract reads in one
    #: place.  The upstream environment is MuJoCo, but the fake backend that this package deploys and checks is a
    #: kinematic stand-in, so the claimed level is F0 and no fixed timestep is asserted.
    fidelity = {
        "engine": "gymnasium:rcs/fr3",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "reset(seed) reseeds the fake's random generator (and cap.world.seed.v1 sets the seed of the "
                     "next reset), so one seed and one action sequence repeat the same state hashes; the upstream "
                     "environment homes the robot and seeds only the wrapper's np_random (base.py:315-317), and no "
                     "upstream run was compared",
        },
        "timestep_ms": 0.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "the deployed fake is a kinematic stand-in: a relative Cartesian offset moves the pose and the gripper "
            "value is applied directly; no MuJoCo rigid-body, contact, actuator or sensor dynamics are run and no "
            "forces are modelled",
            "the registered environment runs MuJoCo inside SimEnv.step_sim and settles each control transition with "
            "step_until_convergence; the clone states a 1 Hz control loop (configs.py:84) but no fixed physics "
            "timestep, so timestep_ms is 0 and ticks do not map to a fixed simulated interval",
            "the camera observations of the registered environment (bird_eye and wrist, 1280x720 at 30 Hz) are NOT "
            "COVERED: the observation space of this package carries robot state only",
            "the fake narrows the three quaternion vector action elements from the upstream's unlimited -inf and inf "
            "to -1 and 1 so every action bound can be exercised; the translation and quaternion scalar bounds follow "
            "base.py:70-79",
            "no wall-clock pacing: realtime_factor 0, so one cap.world.step tick is one control transition and not a "
            "fixed number of simulated seconds",
            "no physical device is modelled; the fake was never compared with an upstream MuJoCo run because the gate "
            "never imports the clone",
            "snapshot and restore are not offered: SimEnv exposes set_replay_state but no get_state/set_state pair",
        ],
    }
