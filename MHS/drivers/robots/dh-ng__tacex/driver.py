"""OpenMHS driver for gh.dh-ng/tacex: the TacEx ball-rolling Isaac Lab task (a Gymnasium family driver).

TacEx is a tactile-simulation extension for Isaac Sim / Isaac Lab (README.md:20-21).  It does not drive a device: it
registers Gymnasium tasks whose ``entry_point`` is an in-tree ``DirectRLEnv`` subclass (base_env.py:235).  This driver
binds the privileged ball-rolling task, ``TacEx-Ball-Rolling-Privileged-v0`` (ball_rolling_privileged/__init__.py:20-31),
which gives a 14-value scalar observation and a five-component task-space action, so the Gymnasium bridge can serve it
through ``cap.world.step.v1``, ``cap.world.reset.v1`` and ``cap.world.seed.v1``.  A GymnasiumDriver is configuration
only; the bridge derives the action schema and limits from the environment's action space.

The task needs Isaac Sim 4.5 and Isaac Lab 2.1.1 on Linux with an NVIDIA GPU (README.md:40-41); the acceptance gate does
not start them and package code never imports the clone.  The ``fake`` backend is this package's pure Python kinematic
stand-in (see fake.py): an F0 model with no physics, IK, tactile sensor or rendering.  The ``sim`` backend would be
``gymnasium.make(env_id)`` (GymnasiumDriver.open_native), but the upstream environments are built with a cfg
(``gym.make(task_name, cfg=env_cfg)``, source/tacex_tasks/test/env_test_utils.py:205) that exists only inside the
Isaac Lab stack, so the simulator path is not configured and was not run.

The ``fidelity`` attribute is the fidelity contract of the model as deployed (spec 05-fidelity FID-002): the analytic
fake on the checked backend, not Isaac Sim's rigid-body model.  Every fact and rule cites a line of the clone at the
pinned commit (adceed41afb7cb48f9ec1f66a662fb8e5a06627f).  This package is model-authored and unreviewed: it is checked
on the fake backend only.
"""

from mhs.driver import Fact, GymnasiumDriver

BASE = "source/tacex_tasks/tacex_tasks/ball_rolling_privileged/base_env.py"
REGISTER = "source/tacex_tasks/tacex_tasks/ball_rolling_privileged/__init__.py"
INSTALL = "docs/source/installation/Local-Installation.md"


class TacExBallRolling(GymnasiumDriver):
    device_id = "tacex-ball-rolling"
    device_kind = "world.sim"
    mode, risk = "simulated", "R0"
    env_id = "TacEx-Ball-Rolling-Privileged-v0"
    native = "tacex_tasks.ball_rolling_privileged.base_env:BallRollingEnv"
    backends = {"fake": ".fake:FakeBallRollingEnv"}
    display_name = "TacEx Ball Rolling (Isaac Lab privileged task)"
    vendor, model = "DH-Ng / Tactile Extension", "TacEx-Ball-Rolling-Privileged-v0"
    tags = ["tacex", "tactile", "isaac-sim", "isaac-lab", "ball-rolling", "reinforcement-learning", "simulation",
            "gymnasium"]
    facts = [
        Fact("TacEx-Ball-Rolling-Privileged-v0 is registered with entry_point "
             "tacex_tasks.ball_rolling_privileged.base_env:BallRollingEnv and disable_env_checker=True",
             source="upstream_code", ref=f"{REGISTER}:20-31"),
        Fact("BallRollingEnv is an Isaac Lab DirectRLEnv subclass configured by BallRollingEnvCfg",
             source="upstream_code", ref=f"{BASE}:235"),
        Fact("The cfg sets decimation to 1 and sim.dt to 0.01 s, so one environment step advances 10 ms",
             source="upstream_code", ref=f"{BASE}:80-83"),
        Fact("The environment computes its step interval as sim.dt times decimation", source="upstream_code",
             ref=f"{BASE}:256"),
        Fact("The configured episode length is 8.3333 / 2 s; the source comment calls it 500 timesteps, but at "
             "dt 0.01 s the quotient is about 416.7", source="upstream_code", ref=f"{BASE}:222"),
        Fact("The action space has five components (dx, dy, dz, droll, dpitch); dyaw is omitted",
             source="upstream_code", ref=f"{BASE}:223"),
        Fact("Every action component is clamped to [-1, 1] before it is passed to the IK controller",
             source="upstream_code", ref=f"{BASE}:381"),
        Fact("The differential IK controller is configured for pose commands in relative mode with the damped "
             "least squares method", source="upstream_code", ref=f"{BASE}:171"),
        Fact("The observation space has 14 values: 3 for the end-effector position, 2 for its roll and pitch, 2 "
             "for the goal, 2 for the object position and 5 for the actions", source="upstream_code",
             ref=f"{BASE}:224-226"),
        Fact("The observation concatenates the end-effector position, its roll and pitch, the object xy position, "
             "the desired goal xy position and the five actions", source="upstream_code", ref=f"{BASE}:588-603"),
        Fact("The success reward has weight 10 and a 0.005 m object-goal threshold", source="upstream_code",
             ref=f"{BASE}:199-203"),
        Fact("The reward adds the success term when the object-goal distance is below "
             "success_reward['threshold']", source="upstream_code", ref=f"{BASE}:480"),
        Fact("The ball is spawned at (0.5, 0, 0.01) m", source="upstream_code", ref=f"{BASE}:188"),
        Fact("The ball radius is 0.005 m", source="upstream_code", ref=f"{BASE}:229"),
        Fact("The object bounds are x in (0.225, 0.75) m and y in (-0.375, 0.375) m, and "
             "too_far_away_threshold is 0.35 m", source="upstream_code", ref=f"{BASE}:230-232"),
        Fact("An episode ends when the object leaves the configured x or y bounds, is more than 1 m from the goal, or "
             "is farther from the end effector than the configured too_far_away_threshold", source="upstream_code",
             ref=f"{BASE}:409-424"),
        Fact("obj_pos_randomization_range lists [-0.1, 0.1] per axis in its first entry and [-0.25, 0.25] in "
             "its second", source="upstream_code", ref=f"{BASE}:219"),
        Fact("The reset sets the goal to the object default position plus a uniform offset in each axis, using the "
             "obj_pos_randomization_range entry indexed by curriculum_phase_id", source="upstream_code",
             ref=f"{BASE}:555-562"),
        Fact("The robot is the Franka Panda arm with a GelSight Mini sensor and stiff PD control", source="upstream_code",
             ref=f"{BASE}:102-103"),
        Fact("The cfg runs 1024 environments in parallel by default", source="upstream_code", ref=f"{BASE}:100"),
        Fact("TacEx requires Isaac Sim 4.5 and Isaac Lab 2.1.1; the installation was tested on Ubuntu 22.04 with a "
             "4090 GPU", source="vendor_doc", ref="README.md:40-41"),
        Fact("The local installation requires Isaac Sim 4.5 and Isaac Lab 2.1.1 on Ubuntu 22.04", source="vendor_doc",
             ref=f"{INSTALL}:2-6"),
    ]
    safe_state = ("the simulation stops advancing: no step or reset is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the environment state is kept and stays readable")
    #: The fidelity contract of the model as deployed (spec 05-fidelity section 2): the package's analytic fake.
    #: The bridge derives the engine, determinism kind and lockstep clock; they are written out so the whole contract
    #: reads in one place.  Isaac Sim's rigid-body model (F1) is not what this backend runs and was never started.
    fidelity = {
        "engine": "gymnasium:TacEx-Ball-Rolling-Privileged-v0",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "reset(seed) or cap.world.seed.v1 resets the fake's Python random.Random and fixes the goal draw, "
                     "and the kinematic update is deterministic; the upstream seed controls Isaac Lab's generators and "
                     "the sample_uniform goal draw, and the two were not compared because the upstream stack was not "
                     "run",
        },
        "timestep_ms": 10.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "kinematic F0 stand-in with no dynamics: no Isaac Sim rigid-body or contact physics, no friction, mass, "
            "IK solver, joint limits, Franka arm or actuator model; the ball follows the end effector kinematically "
            "instead of being pushed by contact forces",
            "the fake's end-effector start pose, push gain and contact radius are placeholders; the upstream start "
            "state comes from the Franka default joint positions and the differential IK controller",
            "only the success term of the reward is modelled (base_env.py:480); the reaching, tracking, orientation, "
            "height, action-rate and joint-velocity terms of the sum are omitted",
            "the tactile, RGB and depth sensors and the rendering pipeline of TacEx are not modelled; this driver "
            "binds the privileged 14-value scalar observation, not the vision or tactile observation groups of the "
            "RGB, depth, Taxim-FOTS or UIPC tasks",
            "the end-effector orientation and the goal height are held at zero in the fake, while the upstream "
            "observation carries the computed roll and pitch and the goal has a fixed z of 0.00125 m (base_env.py:270)",
            "the truncation step is the fake's floor of episode_length_s / dt (416); the upstream comment on "
            "base_env.py:222 says 500 timesteps and the rounding happens in Isaac Lab's DirectRLEnv outside the "
            "clone, so the real count was not verified",
            "the upstream environment is vectorized over 1024 environments by default (base_env.py:100) while the MHS "
            "Gymnasium bridge drives one environment",
            "the upstream stack (Isaac Sim 4.5, Isaac Lab 2.1.1, Linux, an NVIDIA GPU) was never started here, so the "
            "sim backend was not run; the upstream tasks are built with gym.make(task_name, cfg=env_cfg) and the cfg "
            "cannot be constructed without that stack",
            "the fake draws goals with Python's random.Random while the upstream uses Isaac Lab's sample_uniform on "
            "the simulator device, so one seed does not give the same goal on both",
            "snapshot and restore are not offered: the environment exposes no get_state/set_state pair, and the "
            "bridge reports snapshot_restore false",
            "no wall-clock pacing: realtime_factor 0 and clock lockstep, so simulated time advances only with steps",
        ],
    }
