"""OpenMHS driver for gh.qiangwang-academic/ur5e_robot_gym_env_real_and_sim.

The upstream is a legacy Gym reaching task for a simulated UR5 arm in CoppeliaSim:
``Simulation/CoppeliaSim_UR5_gym_v3.py`` defines ``CoppeliaSim_UR5_gym_v3(CoppeliaSim_UR5_base, gym.Env)``.
The bridge publishes the three ``cap.world.*`` classes: ``cap.world.step.v1`` takes ``{ticks, action}``
with ``action = {"values": [four joint increments]}`` bounded by the upstream action space (low -5, high 5),
``cap.world.reset.v1`` takes ``{seed, options}`` and ``cap.world.seed.v1`` takes ``{seed}``.

The package is simulated-only (R0).  The ``fake`` backend is the package's own pure Python stand-in
(``fake.py``); it reproduces the upstream class's public method surface and the upstream movement, reward and
safety-box rules without CoppeliaSim, the remote API or the ``reach_task.ttt`` scene.  The upstream simulator
itself is not served here: the clone never registers a Gym environment id, it imports its siblings as top-level
modules from ``Simulation/``, and it needs the legacy CoppeliaSim remote API at 127.0.0.1:19998 and the
``remoteApi.so`` client library.  Every constant and rule below cites a line of the clone at the pinned commit
513acb7e235ab940fd03c3038208678e285690f3.  The package is model-authored and unreviewed; only the fake backend
is checked.
"""

from mhs.driver import Fact, GymnasiumDriver

V3 = "Simulation/CoppeliaSim_UR5_gym_v3.py"
BASE = "Simulation/CoppeliaSim_UR5_base.py"
ENV = "Simulation/CoppeliaSim_env.py"


class CoppeliaSimUR5GymV3(GymnasiumDriver):
    device_id = "ur5e-reaching-v3"
    env_id = "CoppeliaSim_UR5_gym_v3"
    native = "CoppeliaSim_UR5_gym_v3:CoppeliaSim_UR5_gym_v3"
    backends = {"fake": ".fake:FakeUR5Env"}
    action_space_ref = f"{V3}:45-46"
    display_name = "CoppeliaSim UR5 reaching environment v3 (legacy Gym)"
    vendor, model = "Qiang Wang", "CoppeliaSim_UR5_gym_v3"
    tags = ["ur5", "coppeliasim", "gym", "reaching", "robot-arm", "simulation"]
    facts = [
        Fact("Simulation/README.MD names CoppeliaSim_UR5_gym_v0.py and CoppeliaSim_UR5_gym_v3.py as the "
             "environment code and says its format is gym format", source="vendor_doc",
             ref="Simulation/README.MD:14-15"),
        Fact("The v3 entry class is CoppeliaSim_UR5_gym_v3, a subclass of CoppeliaSim_UR5_base and gym.Env",
             source="upstream_code", ref=f"{V3}:54"),
        Fact("The action_low and action_high lists are [-5, -5, -5, -5] and [5, 5, 5, 5]",
             source="upstream_code", ref=f"{V3}:45-46"),
        Fact("action_space is spaces.Box(low_action, high_action, dtype=np.float32)", source="upstream_code",
             ref=f"{V3}:93-97"),
        Fact("The observation space is a Box of shape (128,128,3) with float32 values from 0 to 255",
             source="upstream_code", ref=f"{V3}:78-89"),
        Fact("The reset target joint vector init_joints_pos is [0.0, 0.0, 0.0, 0.0, pi/2, 0.0]",
             source="upstream_code", ref=f"{V3}:99"),
        Fact("DELTA is pi/180.0 rad and MOVE_UNIT is 2*DELTA", source="upstream_code", ref=f"{V3}:21-33"),
        Fact("apply_action multiplies action[0..3] by MOVE_UNIT and adds it to current_joint_pos[0..3]",
             source="upstream_code", ref=f"{V3}:210-218"),
        Fact("REACH_THRESHOLD is 0.08", source="upstream_code", ref=f"{V3}:22"),
        Fact("check_done reports step_end_status 1 when current_dis is at most REACH_THRESHOLD",
             source="upstream_code", ref=f"{V3}:237-239"),
        Fact("The tip safety box is x [-0.72, 0.72], y [-1.025, 0.275], z [0.66, 1.8]",
             source="upstream_code", ref=f"{V3}:30-32"),
        Fact("check_done reports step_end_status 2 when the tip leaves the safety box",
             source="upstream_code", ref=f"{V3}:247-265"),
        Fact("The joint limits are joint1 [-pi, pi], joint2 [-pi/2, pi/2], joint3 [-pi, pi] and joint4 "
             "[-pi, pi]", source="upstream_code", ref=f"{V3}:38-41"),
        Fact("check_done reports step_end_status 2 when a joint reaches its limit", source="upstream_code",
             ref=f"{V3}:269-297"),
        Fact("STAY_THRESHOLD is 0.1 and STAY_FLAG is 30", source="upstream_code", ref=f"{V3}:26-27"),
        Fact("check_stay returns step_end_status 3 when at least 25 of the last 30 tip positions are within "
             "STAY_THRESHOLD of the current one", source="upstream_code", ref=f"{V3}:321-329"),
        Fact("step rewards (last_dis - current_dis) * 100, pays -150 when step_end_status is 2, and adds "
             "2000 / tra_num_step on reaching the target", source="upstream_code", ref=f"{V3}:164-207"),
        Fact("target_range_low is [-0.343, -0.737, 0.685] and target_range_high is [0.041, -0.003, 0.685]",
             source="upstream_code", ref=f"{BASE}:26-27"),
        Fact("random_gen_one_target_pos draws the next target uniformly between target_range_low and "
             "target_range_high", source="upstream_code", ref=f"{BASE}:111-113"),
        Fact("seed() fills self.np_random with gym.utils.seeding.np_random", source="upstream_code",
             ref=f"{V3}:154-156"),
        Fact("step returns the legacy four-value tuple (next_state, reward, done, info)",
             source="upstream_code", ref=f"{V3}:207"),
        Fact("get_state returns the Side_camera1 image from the simulator", source="upstream_code",
             ref=f"{V3}:158-162"),
        Fact("MAX_STEP is 200", source="upstream_code", ref=f"{V3}:35"),
        Fact("reset sets num_step to 0 and tra_num_step to -1", source="upstream_code", ref=f"{V3}:118-119"),
        Fact("check_done compares num_step with MAX_STEP", source="upstream_code", ref=f"{V3}:241"),
        Fact("apply_action increments tra_num_step, not num_step", source="upstream_code", ref=f"{V3}:231"),
        Fact("The environment opens CoppeliaSim's legacy remote API at 127.0.0.1:19998 before it can run",
             source="upstream_code", ref=f"{ENV}:44"),
        Fact("The recorded environment pins gym 0.18.3, the legacy four-value step API", source="vendor_doc",
             ref="Simulation/requirement_reach.txt:41"),
    ]
    safe_state = ("the simulation stops advancing: no step or reset is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the world state is kept and stays readable")
    fidelity_level = "F0"
    #: The model as deployed is the package's kinematic fake, not the CoppeliaSim engine.  The bridge derives the
    #: clock and reset from the environment; the values below are written out so the whole contract reads in one
    #: place (MHS-005 FID-002).
    fidelity = {
        "engine": "coppeliasim-remote-api:CoppeliaSim_UR5_gym_v3",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "the package's fake draws its target from Python's random.Random(seed), so a seed repeats "
                     "its trajectory; the upstream reset draws the target from numpy's global np.random.uniform "
                     "and its seed() only fills self.np_random, so the two do not share a seed stream",
        },
        "timestep_ms": 0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "the fake is kinematic: it moves the four actuated joints by action * MOVE_UNIT and reads a toy "
            "tip position; it models no rigid-body dynamics, contacts, actuator, sensor, noise or camera rendering",
            "the fake returns a 4x4x3 test image, while the upstream observation_space is 128x128x3 "
            "(Simulation/CoppeliaSim_UR5_gym_v3.py:78-89); the real image size is not carried by the fake",
            "no CoppeliaSim scene is loaded and the legacy remote API at 127.0.0.1:19998 is not contacted, so "
            "the .ttt scene, the real robot part and the simulator's own clock are not exercised",
            "the clone states no fixed physics timestep; timestep_ms is 0 because CoppeliaSim owns the clock",
            "snapshot restore is not offered: get_state returns only the Side_camera1 image and there is no "
            "set_state",
            "the upstream v3 resets itself on reaching, on a safety-box or joint-limit event and on a detected "
            "stay, and its num_step is never incremented, so MAX_STEP 200 is unreachable; the fake mirrors those "
            "transitions without terminating",
            "the fake guards the upstream's 2000 / tra_num_step division when a reach is detected on a first "
            "step; with its toy tip position the reach branch never fires",
            "the fake was never compared with the upstream environment or a real UR5",
        ],
    }
