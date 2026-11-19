"""OpenMHS driver for gh.amazon-far/abc: the ``abc_sim`` bimanual YAM MuJoCo environment (Gymnasium family driver).

A GymnasiumDriver is configuration only: the bridge derives ``cap.world.step.v1``, ``cap.world.reset.v1`` and
``cap.world.seed.v1`` from the environment object.  The step action is a ``Box`` of 14 values in [-1.0, 1.0] in the
order [left_j1..6, left_gripper, right_j1..6, right_gripper] (``abc_sim/env.py:75-76``, ``:175-179``), and the
observation is the environment's dictionary of images, state, masks, prompt and camera timestamps
(``abc_sim/env.py:130-173``).  The device is simulated (R0): no hardware backend, no e-stop path to a machine and no
operator-required limit.

``backends["sim"]`` wraps the upstream factory ``abc_sim.make_env``: it needs the clone's dependencies (``mujoco~=3.8.0``
and ``gymnasium>=1.1``, ``pyproject.toml:15`` and ``:21``) and was not run here.  The acceptance gate runs the
``fake`` backend, a pure-Python kinematic stand-in in fake.py, because the upstream package is not installed where the
gate runs and package code never imports the clone.  The fake's differences from the MuJoCo model are listed in the
fidelity ``gaps`` below and in RESULT.json.

This package is model-authored and unreviewed (``driver.lock.json`` ``authored_by`` is a model, ``reviewed_by`` is
null).  It is checked on the fake backend only; no hardware or ROS backend is declared.
"""

from mhs.driver import Fact, GymnasiumDriver

ENV = "abc_sim/env.py"
CONFIG = "abc_sim/config.py"
README = "abc_sim/README.md"


class ABCYAM(GymnasiumDriver):
    """The ``abc_sim`` bimanual YAM environment served through the Gymnasium bridge."""

    device_id = "abc-yam"
    native = "abc_sim.env:MuJoCoYAMEnv"
    backends = {"fake": ".fake:connect", "sim": ".sim:connect"}
    action_space_ref = f"{ENV}:175-179"
    display_name = "ABC bimanual YAM simulation"
    vendor, model = "Amazon FAR", "ABC YAM"
    tags = ["abc", "yam", "bimanual", "mujoco", "reinforcement-learning", "simulation", "gymnasium"]
    facts = [
        Fact("MuJoCoYAMEnv is a Gymnasium environment (gym.Env) for a bimanual YAM robot whose actions and "
             "observations use the 14D policy-space order [left_j1..6, left_gripper, right_j1..6, right_gripper]",
             source="upstream_code", ref=f"{ENV}:72-77"),
        Fact("The per-step action space is a Box over 14 elements with low -1.0 and high 1.0",
             source="upstream_code", ref=f"{ENV}:124-179"),
        Fact("single_timestep_action_dim is 7 times the number of configured robots, 14 in the base configuration",
             source="upstream_code", ref=f"{ENV}:124-126"),
        Fact("The observation is a Dict with per-camera (3, camera_height, camera_width) uint8 images, a 14-element "
             "float32 state, per-camera Discrete(2) masks, a prompt Text and per-camera float64 timestamps",
             source="upstream_code", ref=f"{ENV}:124-173"),
        Fact("project_policy_state maps MuJoCo qpos into the 14D policy state and clips each gripper element to "
             "qpos/_GRIPPER_CTRL_MAX in [0, 1]", source="upstream_code", ref=f"{ENV}:31-47"),
        Fact("The base configuration defines three cameras (top, left, right) and two robots (left, right), each "
             "robot with seven init_q values", source="upstream_code", ref=f"{CONFIG}:69-123"),
        Fact("get_i2rt_sim_config builds the base configuration, marks every follower as simulation and may override "
             "each robot's init_q from the DEPLOY_INIT_Q environment variable",
             source="upstream_code", ref=f"{CONFIG}:133-145"),
        Fact("reset calls mj_resetData and then restores the arm pose returned by _get_reset_arm_state",
             source="upstream_code", ref=f"{ENV}:304-315"),
        Fact("reset passes options['randomization'] to the task randomizer and may adopt a prompt from the "
             "randomization metadata", source="upstream_code", ref=f"{ENV}:319-336"),
        Fact("reset puts the native randomization outcome into info['randomization'] when it exists",
             source="upstream_code", ref=f"{ENV}:374-378"),
        Fact("RandomizationState.to_dict returns seed, object_states, scale_states and metadata",
             source="upstream_code", ref="abc_sim/randomization/core.py:65-72"),
        Fact("_get_reset_arm_state returns the current 14D arm pose when the arm state is initialized and otherwise "
             "the concatenated init_q; forget_arm_state clears the initialized flag",
             source="upstream_code", ref=f"{ENV}:498-510"),
        Fact("step applies one 14D action and returns the Gymnasium 5-tuple; step_chunk stops at the first terminated "
             "or truncated step", source="upstream_code", ref=f"{ENV}:380-417"),
        Fact("_step_single writes the 14D action into the actuator controls and advance_physics runs "
             "control_decimation mj_step calls", source="upstream_code", ref=f"{ENV}:512-533"),
        Fact("The default physics_dt is 0.002 s and control_decimation is 17, about 0.034 s per control transition",
             source="upstream_code", ref=f"{ENV}:89-90"),
        Fact("terminated is true only when terminate_on_success is set and the task evaluator reports success; "
             "truncated is true when cur_step reaches max_episode_steps and the episode is not terminated",
             source="upstream_code", ref=f"{ENV}:461-468"),
        Fact("The reward is the task evaluator's scalar reward, or 0.0 when no evaluator is attached",
             source="upstream_code", ref=f"{ENV}:451-453"),
        Fact("make_env is the public task-to-environment factory; its default task is 'bottles' and it returns "
             "MuJoCoYAMEnv", source="upstream_code", ref="abc_sim/__init__.py:125-140"),
        Fact("get_obs returns images, masks, state, prompt and camera_timestamps; the masks are all True and the "
             "timestamps are the simulation time", source="upstream_code", ref=f"{ENV}:594-618"),
        Fact("close closes the camera backend", source="upstream_code", ref=f"{ENV}:485-486"),
        Fact("capture_state returns copies of qpos, qvel and the simulated time", source="upstream_code",
             ref=f"{ENV}:476-483"),
        Fact("The runtime dependencies include mujoco~=3.8.0 and gymnasium>=1.1", source="upstream_code",
             ref="pyproject.toml:11-21"),
        Fact("The README documents the stable API: reset(seed, randomize), step(action_14d), step_chunk(action_chunk), "
             "action_space shape (14,) and the observation keys", source="vendor_doc", ref=f"{README}:86-106"),
    ]
    safe_state = ("the simulation stops advancing: after an e-stop no step or reset is accepted until "
                  "mhs.safety.reset clears the latch, and the last observation stays readable")
    #: The fidelity contract of the fake backend (spec 05-fidelity section 2): it is the backend the gate runs.
    #: The upstream MuJoCo route is declared per backend below and was not run.
    fidelity = {
        "engine": "analytic:abc_sim fake kinematic stand-in",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "reset(seed) records the seed and the kinematic transition has no random draw, so one sequence "
                     "of actions repeats exactly on a fresh or forgotten state; the upstream MuJoCo model draws its "
                     "task randomization from the seed",
        },
        "timestep_ms": 34.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "partial",
        "snapshot_restore": False,
        "gaps": [
            "kinematic stand-in: each step makes the commanded 14D policy values the new state; there are no "
            "rigid-body dynamics, contacts, actuators, task evaluator or randomizer, unlike the upstream MuJoCo model",
            "the fake's 14D state is the last commanded policy action; it does not project MuJoCo qpos, so its "
            "gripper element is not clipped and normalized to [0, 1] the way project_policy_state does "
            "(abc_sim/env.py:31-47)",
            "the fake ignores reset options and its seed has no random draw; the upstream passes "
            "options['randomization'] to the task randomizer (abc_sim/env.py:319-336)",
            "the fake supplies a placeholder RandomizationState-shaped metadata fixture, not a sampled scene; "
            "both backends use sim.py to convert the upstream-shaped reset metadata with to_dict() so the "
            "Gymnasium bridge retains it as JSON instead of dropping the info object",
            "the fake returns 3x4x4 placeholder images for the three camera names; the upstream defaults render "
            "3x480x640 per camera (abc_sim/env.py:87-88) and both the size and the camera set are configurable",
            "reset is partial: like the upstream it preserves the current 14D arm pose across resets unless "
            "forget_arm_state() is called (abc_sim/env.py:304-315, :498-510)",
            "no wall-clock pacing: ticks advance simulated time by timestep_ms only",
            "no protocol snapshot: the upstream exposes capture_state() but no set_state(), so snapshot_restore is "
            "false",
            "the fake does not model rewards or success: it returns reward 0.0 and never terminates; upstream also "
            "returns 0.0 when no evaluator is attached",
            "the fake was never compared with the upstream MuJoCo environment; mujoco and gymnasium are not "
            "installed where the gate runs",
        ],
    }
    #: The upstream factory route (abc_sim.make_env), not run here: it builds the real MuJoCo model of the clone.
    fidelity_by_backend = {
        "sim": {
            "engine": "mujoco:abc_sim",
            "fidelity_level": "F1",
            "determinism": {
                "kind": "seeded",
                "seed_control": "parameter",
                "notes": "the upstream reset(seed) drives the task randomizer; the trajectory also depends on the "
                         "scene and on the configured init_q",
            },
            "timestep_ms": 34.0,
            "realtime_factor": 0,
            "clock": "lockstep",
            "reset": "partial",
            "snapshot_restore": False,
            "gaps": [
                "rigid-body MuJoCo model of the bimanual YAM and the task scene; contact and actuator fidelity are "
                "not validated in this package and the route was not run where the gate ran",
                "reset preserves the current 14D arm pose across resets unless forget_arm_state() is called "
                "(abc_sim/env.py:304-315, :498-510)",
                "no wall-clock pacing: only commands advance simulated time",
                "no protocol snapshot: capture_state() has no set_state() counterpart",
                "deployment validation is required: the upstream package needs Python >=3.10, mujoco~=3.8.0, "
                "gymnasium>=1.1 and the downloaded simulator assets (pyproject.toml:10-21, abc_sim/README.md:181-185)",
                "sim.py converts RandomizationState reset metadata through its source-backed to_dict() "
                "method; that adapter was checked only with the package's fake-shaped fixture",
            ],
        },
    }
