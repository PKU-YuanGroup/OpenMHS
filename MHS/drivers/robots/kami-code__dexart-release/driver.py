"""OpenMHS driver for gh.kami-code/dexart-release: the DexArt laptop manipulation environment.

DexArt is a Sapien-backed benchmark for dexterous manipulation of articulated objects (README.md:12-13).  The card's
confirmed entry class is ``dexart.env.rl_env.base:BaseRLEnv``, the legacy ``gym.Env`` base at ``base.py:28``; this
package models its concrete ``laptop`` task (``LaptopRLEnv``, ``laptop_env.py:17``).  ``create_env`` fixes the robot to
``allegro_hand_xarm6_wrist_mounted_face_front`` (``create_env.py:16``), whose robot info declares a 6-DoF arm and a
16-DoF hand (``common_robot_utils.py:53-56``).

The upstream interface is the legacy Gym API: the action space is a ``Box`` from -1 to 1 with ``action_dim``
elements (``base.py:597-599``), the observation space is an unbounded ``Box`` with ``obs_dim`` elements
(``base.py:601-606``), ``reset`` returns only the observation and ignores its seed argument (``laptop_env.py:104-123``)
and ``step`` returns the four-value ``(obs, reward, done, info)`` tuple (``base.py:216-229``).  The Gymnasium bridge
handles that legacy shape, so the card's ``GymnasiumDriver`` decision is used as-is.

The gate cannot import the upstream stack (``gym``, ``numpy``, ``sapien``, ``transforms3d`` and the separately
downloaded assets, README.md:35-37), and package code never imports or runs the clone.  The ``fake`` backend is this
package's own pure-Python kinematic stand-in for the ``BaseRLEnv`` surface the bridge uses; it was never compared with
an upstream run and does not model the Sapien physics.  That is why the published fidelity is F0 (kinematic), not the
F1 of the upstream Sapien model, and the gaps say so.  The package is model-authored and unreviewed; it is checked on
the fake backend only and claims no hardware run.
"""

from mhs.driver import Fact, GymnasiumDriver

BASE = "dexart/env/rl_env/base.py"
LAPTOP = "dexart/env/rl_env/laptop_env.py"
LAPTOP_SIM = "dexart/env/sim_env/laptop_env.py"
ROBOT = "dexart/utils/common_robot_utils.py"
CREATE = "dexart/env/create_env.py"


class DexArtLaptop(GymnasiumDriver):
    device_id = "dexart-laptop"
    device_kind = "world.sim"
    mode = "simulated"
    risk = "R0"
    native = "dexart.env.rl_env.base:BaseRLEnv"
    backends = {"fake": ".fake:FakeDexArtLaptop"}
    env_id = None
    display_name = "DexArt laptop task (allegro hand + xArm6, Sapien)"
    vendor, model = "Kami-code", "DexArt laptop task"
    tags = ["dexart", "sapien", "dexterous-manipulation", "articulated-objects", "reinforcement-learning",
            "simulation", "gym"]
    facts = [
        Fact("DexArt is a benchmark for dexterous manipulation of articulated objects, and the repository contains "
             "the simulated environment and training code", source="vendor_doc", ref="README.md:12-13"),
        Fact("create_env fixes robot_name to allegro_hand_xarm6_wrist_mounted_face_front", source="upstream_code",
             ref=f"{CREATE}:16"),
        Fact("create_env dispatches the task names faucet, bucket, laptop and toilet to the four RL environment "
             "classes and raises NotImplementedError for any other name", source="upstream_code",
             ref=f"{CREATE}:32-41"),
        Fact("create_env defaults index to -1", source="upstream_code", ref=f"{CREATE}:13-15"),
        Fact("The robot info for allegro_hand_xarm6_wrist_mounted_face_front declares hand_dof 16 and arm_dof 6",
             source="upstream_code", ref=f"{ROBOT}:53-56"),
        Fact("BaseRLEnv.action_dim returns self.robot.dof", source="upstream_code", ref=f"{BASE}:90-92"),
        Fact("action_space is a Box from -1 to 1 with action_dim elements", source="upstream_code",
             ref=f"{BASE}:597-599"),
        Fact("observation_space is a Box bounded by -inf and inf with obs_dim elements", source="upstream_code",
             ref=f"{BASE}:601-606"),
        Fact("The laptop oracle observation concatenates the robot joint positions, the palm linear velocity (3), "
             "the palm angular velocity (3), the palm position (3) and the progress fraction (1)",
             source="upstream_code", ref=f"{LAPTOP}:71-75"),
        Fact("LaptopRLEnv.reset accepts seed, return_info and options but its body never reads them, and it returns "
             "only the observation", source="upstream_code", ref=f"{LAPTOP}:104-123"),
        Fact("BaseRLEnv.step returns the four-value (obs, reward, done, info) tuple; reaching the horizon sets "
             "done True and records TimeLimit.truncated as not done", source="upstream_code", ref=f"{BASE}:216-229"),
        Fact("The laptop environment reports a horizon of 250 steps", source="upstream_code", ref=f"{LAPTOP}:146-148"),
        Fact("The laptop simulation scene sets its physics timestep to 0.004 s", source="upstream_code",
             ref=f"{LAPTOP_SIM}:25"),
        Fact("create_env defaults frame_skip to 10", source="upstream_code", ref=f"{CREATE}:13-15"),
        Fact("BaseRLEnv computes control_time_step as the scene timestep times frame_skip", source="upstream_code",
             ref=f"{BASE}:123-125"),
        Fact("The laptop simulation sets change_instance_when_reset when index is -1", source="upstream_code",
             ref=f"{LAPTOP_SIM}:44-47"),
        Fact("The laptop simulation reset_env draws the articulated-object instance with the global random module's "
             "randint when change_instance_when_reset is set", source="upstream_code", ref=f"{LAPTOP_SIM}:120-125"),
        Fact("The install requirements are transforms3d, gym 0.25.2, sapien 2.2.1, numpy and open3d 0.14.1",
             source="upstream_code", ref="setup.py:16-18"),
        Fact("The README instructs downloading the assets separately and placing the asset directory at the project "
             "root", source="vendor_doc", ref="README.md:35-37"),
    ]
    safe_state = ("the simulation stops advancing: after an e-stop the runtime's software latch refuses step, reset "
                  "and seed until mhs.safety.reset clears it, the last world state stays readable, and no native stop "
                  "method exists in a simulated environment")
    #: The bridge serves a seed and an options object on reset.  The upstream signature accepts both but reads
    #: neither (laptop_env.py:104-123); the fake uses the seed for its own initial draw, which the descriptions say.
    _RESET_INPUTS = {
        "seed": {"type": "integer", "minimum": 0,
                 "description": "Seed for the fake's initial draw; the upstream reset accepts but does not use it"},
        "options": {"type": "object",
                    "description": "Accepted by the upstream reset signature but not read by it"},
    }
    #: The complete fidelity contract of the model as deployed (spec 05-fidelity section 2).  The only runnable
    #: backend is the kinematic fake, so the package claims F0 and does not claim the upstream Sapien dynamics; the
    #: gaps name what is missing and that an upstream run was not made.
    fidelity = {
        "engine": "analytic:dexart-laptop",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "the fake seeds Python's random.Random from the reset seed, so one seed repeats its trajectory; "
                     "upstream reset accepts a seed but does not use it (laptop_env.py:104-123), and the articulated "
                     "object instance is drawn with the global random module (sim_env/laptop_env.py:120-125), so no "
                     "seed-repeat claim is made for an upstream run",
        },
        "timestep_ms": 40.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "the fake is kinematic: it integrates the 22 action values into a joint-position vector and models no "
            "Sapien rigid-body dynamics, contacts, friction, inverse kinematics, motors, grasp physics or articulated "
            "object constraints",
            "the upstream model is F1 (Sapien rigid-body dynamics with contacts); this package publishes F0 because "
            "the only runnable backend is the fake and no upstream run was made",
            "one tick is one environment step: upstream that step integrates frame_skip 10 physics steps of 0.004 s "
            "(create_env.py:14, sim_env/laptop_env.py:25), so the physics timestep is 4 ms and the control period is "
            "40 ms; timestep_ms names the control period the bridge advances",
            "the observation is the real laptop oracle layout and length (22 joint positions plus 10 palm and "
            "progress values, laptop_env.py:71-75) but its values are a stand-in; no visual observation, camera, "
            "point cloud or imagination array is modelled (NOT COVERED: the visual observation Dict)",
            "the fake draws its initial state with Python's random.Random and ignores reset options, while the "
            "upstream reset ignores its seed and selects the object instance with the global random module",
            "the fake was never compared with the upstream environment; the clone needs the Sapien stack and the "
            "separately downloaded assets (README.md:35-37), which the gate cannot import",
            "no wall-clock pacing: realtime_factor 0, and only commands advance simulated time",
            "snapshot and restore are not offered: BaseRLEnv exposes no get_state/set_state",
        ],
    }
