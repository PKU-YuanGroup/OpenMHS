"""OpenMHS driver for gh.neuracoreai/bigym: the ``DrawerTopOpen`` cupboard task (a Gymnasium family driver).

BiGym is a MuJoCo/Gymnasium benchmark whose tasks are instantiated directly (README.md:82), not registered with
``gymnasium.make``.  This driver names the concrete task class ``bigym.envs.cupboards:DrawerTopOpen`` and serves the
``cap.world.step.v1``, ``cap.world.reset.v1`` and ``cap.world.seed.v1`` contract through the Gymnasium family bridge.
The device is a simulator (R0): there is no hardware backend, no physical e-stop and no operator-required bound.

The action space is built by the environment's configured action mode at construction time
(``bigym/bigym_env.py:106-108``), so it is not a fixed property of the task class.  This package models the default
H1 configuration with ``JointPositionActionMode(floating_base=True, absolute=False)`` and the Robotiq 2F85 gripper:
the fake's 15-element Box is a stand-in for that configuration.  The bridge derives the served limits from that Box;
they are the fake's, not a citation of the upstream space, because no single upstream line states all the bounds.
Other action modes, floating-DOF sets, robots, control frequencies or gripper configurations change the shape and
bounds.  The ``sim`` backend is not declared; the upstream environment was not run and is never imported.

The fake backend is an analytic task-level stand-in (fidelity F0), not a recording and not the upstream MuJoCo
model.  It uses the upstream success, failure, reward, termination and truncation predicates on a small fake state.
This package is model-authored and unreviewed: it is checked on the fake backend only.
"""

from mhs.driver import Fact, GymnasiumDriver


class DrawerTopOpen(GymnasiumDriver):
    device_id = "bigym-drawer-top-open"
    env_id = "bigym:DrawerTopOpen"
    native = "bigym.envs.cupboards:DrawerTopOpen"
    backends = {"fake": ".fake:FakeDrawerTopOpen"}
    display_name = "BiGym DrawerTopOpen (H1 analytic fake)"
    vendor, model = "NeuracoreAI", "BiGym v4.1.0 DrawerTopOpen"
    tags = ["bigym", "cupboards", "drawer", "manipulation", "mobile-manipulation", "h1", "mujoco", "gymnasium",
            "simulation"]
    facts = [
        Fact("DrawerTopOpen succeeds when the last normalized joint value of the base cabinet's drawer state is "
             "within TOLERANCE of 1", source="upstream_code", ref="bigym/envs/cupboards.py:34-38"),
        Fact("TOLERANCE is 0.1", source="upstream_code", ref="bigym/envs/cupboards.py:11"),
        Fact("The cupboard task base selects the counter_base_wall_3x1 preset and exposes its first BaseCabinet as "
             "cabinet_drawers", source="upstream_code", ref="bigym/envs/cupboards.py:14-25"),
        Fact("The first BaseCabinet of that preset enables big drawer 1 and small drawers 3 and 4",
             source="upstream_code", ref="bigym/envs/presets/counter_base_wall_3x1.yaml:3-7"),
        Fact("BaseCabinet.get_state returns the normalized position of every joint of the cabinet body",
             source="upstream_code", ref="bigym/envs/props/cabintets.py:21-28"),
        Fact("BiGymEnv is a Gymnasium environment whose default robot is H1", source="upstream_code",
             ref="bigym/bigym_env.py:34-48"),
        Fact("The control frequency is bounded to 20..500 Hz and the physics timestep is 0.002 s",
             source="upstream_code", ref="bigym/bigym_env.py:25-28"),
        Fact("The control_frequency constructor parameter defaults to CONTROL_FREQUENCY_MAX",
             source="upstream_code", ref="bigym/bigym_env.py:53-59"),
        Fact("The environment takes round(500/control_frequency) physics substeps per control call",
             source="upstream_code", ref="bigym/bigym_env.py:95-98"),
        Fact("The action space is built by the configured action mode with action_scale equal to the substep count",
             source="upstream_code", ref="bigym/bigym_env.py:106-108"),
        Fact("JointPositionActionMode builds a Box from the floating-base delta bounds, the limb control range and "
             "the gripper range", source="upstream_code", ref="bigym/action_modes.py:208-232"),
        Fact("The H1 floating-base delta ranges are -0.01..0.01 for translation and -0.05..0.05 for rotation",
             source="upstream_code", ref="bigym/robots/configs/h1.py:126-127"),
        Fact("The H1 limb delta action range is -0.1..0.1", source="upstream_code",
             ref="bigym/robots/configs/h1.py:145-147"),
        Fact("The Robotiq 2F85 gripper control range is 0..1", source="upstream_code",
             ref="bigym/robots/configs/robotiq.py:7-10"),
        Fact("The observation space is a Dict with proprioception and proprioception_grippers; a floating base adds "
             "floating-base position and accumulated-action arrays", source="upstream_code",
             ref="bigym/bigym_env.py:252-288"),
        Fact("The default ObservationConfig has no cameras, proprioception on and privileged information off",
             source="upstream_code", ref="bigym/utils/observation_config.py:49-55"),
        Fact("reset(seed, options) updates the seed, resets physics, action and robot, calls _on_reset and returns "
             "(observation, info)", source="upstream_code", ref="bigym/bigym_env.py:392-406"),
        Fact("step rejects an action with a wrong shape or outside the action space before stepping",
             source="upstream_code", ref="bigym/bigym_env.py:449-465"),
        Fact("step returns (observation, reward, terminated, truncated, info)", source="upstream_code",
             ref="bigym/bigym_env.py:420-447"),
        Fact("terminate is success or fail and truncate is not is_healthy", source="upstream_code",
             ref="bigym/bigym_env.py:163-171"),
        Fact("reward is success times SPARSE_REWARD_FACTOR", source="upstream_code",
             ref="bigym/bigym_env.py:494-496"),
        Fact("fail is true when the pelvis position norm exceeds MAX_DISTANCE_FROM_ORIGIN", source="upstream_code",
             ref="bigym/bigym_env.py:478-492"),
        Fact("MAX_DISTANCE_FROM_ORIGIN is 10", source="upstream_code", ref="bigym/bigym_env.py:30"),
        Fact("The cupboards reset robot position is [-0.2, 0, 0]", source="upstream_code",
             ref="bigym/envs/cupboards.py:17"),
        Fact("The README says tasks are instantiated directly", source="vendor_doc", ref="README.md:82"),
    ]
    safe_state = ("the simulation stops advancing: no step or reset is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the environment state is kept and stays readable")
    #: The deployed fake is an analytic model: F0, no rigid-body dynamics.  See the gaps.
    fidelity = {
        "engine": "analytic:bigym-DrawerTopOpen",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "reset(seed) accepts and records a seed and the fake's state transitions are deterministic, "
                     "so the same seed and actions repeat the bridge state hashes; the fake does not draw its "
                     "initial state from the seed, while upstream seeds numpy, so this is not a claim that a seed "
                     "gives the same trajectory as the upstream MuJoCo model",
        },
        "timestep_ms": 2.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "no rigid-body dynamics, contacts, actuators or sensors: the fake integrates the floating base as a "
            "point, uses its x and y values for the 10 m failure distance, and moves the last drawer with the "
            "mean arm action, so forces, collisions and trajectories are not modelled and do not match MuJoCo",
            "no wall-clock pacing: realtime_factor 0; one fake control step is mapped to 2 ms because the default "
            "control frequency is 500 Hz and PHYSICS_DT is 0.002 s (bigym/bigym_env.py:25-28), not because the "
            "fake measures time",
            "the observation arrays are shorter than upstream's: the fake returns 4 proprioception values instead "
            "of len(robot.qpos)+len(robot.qvel) (the H1 model and action mode determine the real length), 2 "
            "gripper values, and 3 floating-base position and accumulated-action values; the observation lengths "
            "are stand-ins",
            "the action space is a 15-element stand-in for the default H1 "
            "JointPositionActionMode(floating_base=True, absolute=False) and Robotiq 2F85 configuration (3 "
            "floating-base, 10 arm/wrist and 2 gripper values); upstream builds it from the loaded model at "
            "construction time, so other action modes, robots, floating-DOF sets, control frequencies or gripper "
            "configurations change the shape and bounds, and this fake was not compared with the upstream "
            "environment",
            "gymnasium, MuJoCo, dm_control and mojo are not imported by this package; no upstream environment was "
            "run and no recorded traffic is replayed",
            "the fake has no simulation health monitor: truncation stays false unless a test sets its health flag; "
            "camera, depth and privileged observations and rendering are not modelled because the default "
            "ObservationConfig has no cameras",
        ],
    }
