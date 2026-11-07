"""OpenMHS driver for gh.masato-ka/gym-soarm: the SoArm-v0 Gymnasium environment (a Gymnasium family driver).

``SoArm-v0`` is the registered form of ``gym_soarm.env:SoArmAlohaEnv`` (gym_soarm/__init__.py:25-34).  A
GymnasiumDriver is configuration only: ``env_id`` names the environment and the bridge derives the contract from its
spaces.  ``cap.world.step.v1`` takes ``{ticks, action}`` where the action is ``{"values": [6 joint positions]}``
bounded by the environment's action Box; ``cap.world.reset.v1`` takes ``{seed, options}`` and ``cap.world.seed.v1``
``{seed}``.  The device is a simulated world (R0): there is no hardware backend and no operator-required limit.

The clone is not importable here: it needs gymnasium, numpy, dm-control and MuJoCo (pyproject.toml:21-26) and
``gym_soarm/tasks/sim.py`` imports torch, lerobot and a missing ``.reward_wrapper`` module (sim.py:1-16).  The
``fake`` backend is therefore the package's own pure Python environment (fake.py), built from the spaces and the
reset/step semantics of the upstream class.  A backend name that ``backends`` does not list (``sim``) is served by
``gymnasium.make("SoArm-v0")`` through GymnasiumDriver.open_native; that path needs the installed upstream package and
was not run here.

The ``fidelity`` attribute is the fidelity contract of the model as deployed (spec 05-fidelity FID-002): the fake is
a kinematic stand-in (F0), not the upstream MuJoCo simulation (which would be F1).  Every constant and rule cites a
line of the clone at the pinned commit (d1e47309120a372cf95169a555bda64704c9cf40).  This package is model-authored
and unreviewed; it is checked on the fake backend only.
"""

from mhs.driver import Fact, GymnasiumDriver

ENV = "gym_soarm/env.py"
CONSTANTS = "gym_soarm/constants.py"
INIT = "gym_soarm/__init__.py"
SIM = "gym_soarm/tasks/sim.py"


class SoArm100(GymnasiumDriver):
    device_id = "so-arm100"
    env_id = "SoArm-v0"
    native = "gym_soarm.env:SoArmAlohaEnv"
    backends = {"fake": ".fake:FakeSoArmAlohaEnv"}
    action_space_ref = f"{CONSTANTS}:21-28"
    display_name = "SO-ARM100 single-arm manipulation environment (Gymnasium SoArm-v0)"
    vendor, model = "Masato Kawamura", "SO-ARM100"
    tags = ["robot-arm", "so-arm100", "manipulation", "reinforcement-learning", "simulation", "gymnasium"]
    facts = [
        Fact("SoArm-v0 is registered with entry point gym_soarm.env:SoArmAlohaEnv, max_episode_steps 200, and "
             "defaults task pick_place, obs_type pixels_agent_pos, render_mode rgb_array and camera_config "
             "front_wrist", source="upstream_code", ref=f"{INIT}:25-34"),
        Fact("The environment declares render modes rgb_array and human and render_fps 50", source="upstream_code",
             ref=f"{ENV}:20"),
        Fact("The action space is a Box of six absolute joint positions for shoulder_pan, shoulder_lift, elbow_flex, "
             "wrist_flex, wrist_roll and gripper", source="upstream_code", ref=f"{ENV}:103-110"),
        Fact("The joint limits are shoulder_pan -1.91986 to 1.91986, shoulder_lift -1.74533 to 1.74533, elbow_flex "
             "-1.69 to 1.69, wrist_flex -1.65806 to 1.65806, wrist_roll -2.74385 to 2.84121 and gripper -0.17453 "
             "to 1.74533", source="upstream_code", ref=f"{CONSTANTS}:21-28"),
        Fact("The joint angles are in radians: the start-pose comment says in radians and the README displays joint "
             "angles in radians", source="vendor_doc", ref="README.md:84-87"),
        Fact("The simulation timestep is DT = 0.02 s (50 Hz)", source="upstream_code", ref=f"{CONSTANTS}:4-5"),
        Fact("The dm_control Environment is created with control_timestep=DT and an infinite time limit",
             source="upstream_code", ref=f"{ENV}:224-240"),
        Fact("The starting arm pose is [0.0, 0.0, -1.57, 0.0, 0.0, 0.0] radians", source="upstream_code",
             ref=f"{CONSTANTS}:30-38"),
        Fact("The gripper observation is normalized to [0, 1] with 0 closed and 1 open: (x - (-0.17453)) / "
             "(1.74533 - (-0.17453))", source="upstream_code", ref=f"{CONSTANTS}:42-57"),
        Fact("The agent_pos observation is the five arm joint positions followed by the normalized gripper position",
             source="upstream_code", ref=f"{SIM}:144-151"),
        Fact("The observation types are state (6 joint positions, 6 velocities, end-effector position and "
             "quaternion), pixels (a Dict of camera images) and pixels_agent_pos (pixels plus 6 joint positions)",
             source="upstream_code", ref=f"{ENV}:60-101"),
        Fact("camera_config front_wrist includes front_camera and wrist_camera; the four accepted values are "
             "front_only, front_wrist, diagonal_wrist and all", source="upstream_code", ref=f"{ENV}:112-123"),
        Fact("The task renders four camera images at height 480 and width 640: front_camera, wrist_camera, "
             "diagonal_camera and overview_camera", source="upstream_code", ref=f"{SIM}:188-192"),
        Fact("A reset seeds the task random generators with the given seed", source="upstream_code",
             ref=f"{ENV}:293-296"),
        Fact("PickPlaceTask.initialize_episode draws the cube placement from a time-based seed, so the reset seed "
             "does not make the pick_place placement repeatable", source="upstream_code", ref=f"{SIM}:246-249"),
        Fact("The reset options accept cube_grid_position 0 to 8, -1 with cube_x and cube_y for custom coordinates, "
             "or None for random placement, and values outside the grid range raise ValueError",
             source="upstream_code", ref=f"{ENV}:276-291"),
        Fact("The blue cube grid is 3x3 around table centre (0.0, 0.4) with +-0.10 m in x and +-0.075 m in y, at "
             "z = 0.05 m", source="upstream_code", ref=f"{SIM}:251-276"),
        Fact("The goal plate starts at (-0.2, 0.4, 0.05) in the scene model", source="upstream_code",
             ref="gym_soarm/assets/scene.xml:33"),
        Fact("step clips the action to the joint limits before it advances the dm_control physics",
             source="upstream_code", ref=f"{ENV}:311-317"),
        Fact("SoArmAlohaEnv.step always returns truncated=False", source="upstream_code", ref=f"{ENV}:329-330"),
        Fact("An episode terminates when the blue cube is within 10 mm of the goal plate", source="upstream_code",
             ref=f"{SIM}:401-419"),
        Fact("The pick_place reward is 1 - d / 1.0, clipped to 0, where d is the Euclidean distance between the "
             "forward-kinematics end-effector position and the blue cube, and the reward is 0 beyond 1.0 m",
             source="upstream_code", ref=f"{SIM}:321-361"),
        Fact("The forward kinematics maps the first five joint angles to the end-effector position with the "
             "SO-ARM101 link offsets", source="upstream_code", ref=f"{SIM}:18-107"),
        Fact("The environment depends on mujoco, gymnasium, dm-control and imageio", source="upstream_code",
             ref="pyproject.toml:21-26"),
        Fact("The task module imports torch, lerobot and a .reward_wrapper module", source="upstream_code",
             ref=f"{SIM}:1-16"),
    ]
    safe_state = ("the simulation stops advancing: no step or reset is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the last observation stays readable")
    #: The fidelity contract of the model as deployed (spec 05-fidelity section 2).  The bridge derives the engine,
    #: the determinism kind and the lockstep clock; they are written out so the whole contract reads in one place.
    fidelity = {
        "engine": "gymnasium:SoArm-v0",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "the fake's cube placement and joint model are deterministic for one seed and action sequence; "
                     "the upstream PickPlaceTask samples the cube from the wall clock (sim.py:246-249), so the "
                     "upstream reset is not reproducible in the same way",
        },
        "timestep_ms": 20.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "kinematic stand-in: each joint moves toward the requested position by a bounded placeholder delta per "
            "tick; there is no dynamics, contact, friction, actuator, sensor or noise model, and the upstream "
            "dm_control/MuJoCo physics (pyproject.toml:23-25) was not run",
            "the camera observations are 2x2x3 placeholder frames; the real environment renders 480x640x3 per "
            "camera (sim.py:188-192), and the stand-in frames carry no scene content",
            "the blue cube stays where reset placed it because there is no contact or grasping model, so "
            "termination occurs only when a reset places the cube on the goal plate; the stacking task is not "
            "modelled by the fake",
            "no wall-clock pacing: realtime_factor 0, and ticks advance simulated time by timestep_ms only",
            "no physical device is modelled and the model was never validated against one",
            "snapshot and restore are not offered: the environment exposes no get_state or set_state",
            "the clone itself is not importable here: tasks/sim.py imports torch, lerobot and a missing "
            "reward_wrapper module (sim.py:1-16), so the upstream sim backend was not run",
        ],
    }
