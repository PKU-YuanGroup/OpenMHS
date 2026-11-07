"""OpenMHS driver for gh.snu-pi/humanoidtoolbench: the G1BallMove-L0-S condition (a Gymnasium family driver).

The upstream repository registers 18 Gymnasium conditions (``humanoidtoolbench/<scenario>-L<level>-<mode>``,
``src/humanoidtoolbench/envs/__init__.py:25-38``).  This package serves the documented default condition,
``humanoidtoolbench/G1BallMove-L0-S`` (``docs/ENVIRONMENTS.md:11-15``), through the card's AST-confirmed entry class
``humanoidtoolbench.envs.sonic_loco_manip:SonicLocoManipEnv``.  A GymnasiumDriver is configuration only: ``env_id``
names the environment and the bridge derives ``cap.world.step.v1``, ``cap.world.reset.v1`` and ``cap.world.seed.v1``
from the environment's spaces.

The real action space is the task controller's ``Dict`` of seven joint-position ``Box`` spaces (43 whole-body joints:
6 left leg, 6 right leg, 3 waist, 7 left arm, 7 right arm, 7 left hand and 7 right hand,
``src/humanoidtoolbench/robots/g1_sonic.py:32-94,118`` and
``src/humanoidtoolbench/robots/controllers/combo.py:44-56``).  The leg, waist and arm controllers bound every joint to
-1 to 1 (``controllers/qpos.py:22-23``); the hand controllers bound every joint to -pi to pi
(``controllers/eef.py:18-22``).  The observation space starts with ``joint_qpos``, a 43-value Box from -pi to pi
(``tasks/g1_toolbench_tabletop.py:165-174``), and the real observation also carries the head stereo pair and two wrist
camera streams (``tasks/g1_toolbench_tabletop.py:86-120``).

The device is simulated (R0).  There is no hardware backend, no e-stop path to a machine and no operator-required
limit.  The gate cannot import the upstream package (it needs MuJoCo, torch, gear_sonic and decoupled-wbc, and package
code never imports the clone), so ``fake.py`` is the package's own pure Python stand-in.  A backend name that
``backends`` does not list (``sim``) is served by ``gymnasium.make(env_id)``; that path was not run, and the registered
environment needs the evaluator's ``sonic_config`` keyword (``cli/eval_decoupled_wbc.py:154-161``).

The ``fidelity`` attribute describes the model as deployed on the fake backend: a kinematic 43-joint stand-in with no
dynamics (F0).  It names the 5 ms physics step and the 20 ms control step separately, as MHS-005 FID-015 requires when
a native model decimates, and its ``gaps`` state what is not modelled.  This package is model-authored and unreviewed:
it is checked on the fake backend only.
"""

from mhs.driver import Fact, GymnasiumDriver

REGISTER = "src/humanoidtoolbench/envs/__init__.py"
ENV = "src/humanoidtoolbench/envs/sonic_loco_manip.py"
TASK = "src/humanoidtoolbench/tasks/g1_toolbench_tabletop.py"
ROBOT = "src/humanoidtoolbench/robots/g1_sonic.py"


class HumanoidToolBenchG1BallMoveL0S(GymnasiumDriver):
    device_id = "humanoidtoolbench"
    env_id = "humanoidtoolbench/G1BallMove-L0-S"
    native = "humanoidtoolbench.envs.sonic_loco_manip:SonicLocoManipEnv"
    backends = {"fake": ".fake:FakeSonicLocoManipEnv"}
    display_name = "HumanoidToolBench G1BallMove-L0-S (MuJoCo G1 tool-use simulation)"
    vendor, model = "SNU-PI", "HumanoidToolBench G1BallMove-L0-S"
    tags = ["humanoid", "humanoidtoolbench", "mujoco", "tool-use", "reinforcement-learning", "simulation", "gymnasium"]
    facts = [
        Fact("Every condition is registered as humanoidtoolbench/{scenario}-L{level}-{mode} for the three scenarios, "
             "three levels and two modes, with entry point humanoidtoolbench.envs.sonic_loco_manip:SonicLocoManipEnv",
             source="upstream_code", ref=f"{REGISTER}:25-38"),
        Fact("Every cell is registered with max_episode_steps=3000, one minute at the 50 Hz control rate",
             source="upstream_code", ref=f"{REGISTER}:27-37"),
        Fact("Environment IDs have the form humanoidtoolbench/G1<Scenario>-L<level>-<mode>; the default condition is "
             "G1BallMove-L0-S", source="vendor_doc", ref="docs/ENVIRONMENTS.md:11-15"),
        Fact("Every condition uses 3000 policy-control steps per episode at 50 Hz", source="vendor_doc",
             ref="docs/ENVIRONMENTS.md:3-7"),
        Fact("SonicLocoManipEnv.reset takes seed and options and returns (observation, info); step takes one action "
             "and returns (observation, reward, terminated, truncated, info)", source="upstream_code",
             ref=f"{ENV}:57-99"),
        Fact("A control step applies the action and advances the simulator control_decimal times, where "
             "control_decimal = (1/physics_dt)/render_hz", source="upstream_code", ref=f"{ENV}:70-80"),
        Fact("The task metadata declares physics_dt 0.005 s, control_hz 200 and render_hz 50", source="upstream_code",
             ref=f"{TASK}:70-73"),
        Fact("The G1 whole-body robot has wholebody_dof 43", source="upstream_code", ref=f"{ROBOT}:118"),
        Fact("The whole-body joint list is 6 left leg, 6 right leg, 3 waist, 7 left arm, 7 right arm, 7 left hand and "
             "7 right hand joints", source="upstream_code", ref=f"{ROBOT}:32-94"),
        Fact("The action space is a Dict of seven Box spaces named left_leg, right_leg, waist, left_arm, right_arm, "
             "left_eef and right_eef", source="upstream_code",
             ref="src/humanoidtoolbench/robots/controllers/combo.py:44-56"),
        Fact("The leg, waist and arm joint-position controllers bound every joint to -1 to 1", source="upstream_code",
             ref="src/humanoidtoolbench/robots/controllers/qpos.py:22-23"),
        Fact("The dexterous-hand controllers bound every hand joint to -pi to pi", source="upstream_code",
             ref="src/humanoidtoolbench/robots/controllers/eef.py:18-22"),
        Fact("The observation space starts with joint_qpos, a Box from -pi to pi with shape wholebody_dof",
             source="upstream_code", ref=f"{TASK}:165-174"),
        Fact("The observation space also declares a head stereo pair and left and right wrist camera spaces",
             source="upstream_code", ref=f"{TASK}:86-120"),
        Fact("A camera observation space is a Box from 0 to 255 with shape (height, width, 3)", source="upstream_code",
             ref="src/humanoidtoolbench/sensors/config.py:45-48"),
        Fact("Every camera stream is 640 by 360 pixels", source="upstream_code", ref=f"{TASK}:38-41"),
        Fact("The environment returns joint_qpos as a float32 array from the MuJoCo simulator, and render_obs decides "
             "whether camera frames are added", source="upstream_code", ref=f"{ENV}:40-48"),
        Fact("The environment terminates on task success or failure and its step returns truncated False",
             source="upstream_code", ref=f"{ENV}:86-99"),
        Fact("The reward is the task's compute_reward result; ToolReasoningTask returns the lifted height fraction",
             source="upstream_code", ref="src/humanoidtoolbench/tasks/tool_reasoning.py:316-318"),
        Fact("Task.reset(seed) seeds the layout randomizers: DRManager.reset sets Python's random and numpy seeds when "
             "a seed is given", source="upstream_code", ref="src/humanoidtoolbench/dr/manager.py:29-36"),
        Fact("SonicLocoManipEnv.__init__ requires a sonic_config mapping", source="upstream_code", ref=f"{ENV}:22-39"),
        Fact("The evaluation CLI creates the environment with gym.make and passes split, sim_mode, physics_dt, "
             "headless and sonic_config", source="upstream_code",
             ref="src/humanoidtoolbench/cli/eval_decoupled_wbc.py:154-161"),
        Fact("The project requires Python 3.10.* and depends on mujoco 3.11.0, gymnasium > 0.29.1, numpy 1.26.4, "
             "torch 2.7.0 and gear_sonic", source="upstream_code", ref="pyproject.toml:8-22"),
        Fact("The README requires Linux x86_64 with an NVIDIA GPU and EGL headless rendering", source="vendor_doc",
             ref="README.md:20-28"),
        Fact("The docs describe a (T, 36) policy action chunk of 50 Hz controller commands, separate from the "
             "environment action vector", source="vendor_doc", ref="docs/PUBLIC_EVALUATION.md:246-259"),
        Fact("The docs state joint angles and angular commands use radians, base height metres and navigation "
             "velocities metres per second", source="vendor_doc", ref="docs/PUBLIC_EVALUATION.md:261-266"),
        Fact("The docs state the raw robot observation has 43 joint values and the policy state excludes the leg "
             "joints", source="vendor_doc", ref="docs/PUBLIC_EVALUATION.md:267-269"),
    ]
    safe_state = ("the simulation stops advancing: after an e-stop the runtime refuses every step and reset until "
                  "mhs.safety.reset clears the latch, and the last world state stays readable; the simulator has no "
                  "native stop")
    fidelity_level = "F0"
    #: The fidelity contract of the fake model as deployed (MHS-005 section 2).  The bridge derives the engine string
    #: and the lockstep clock; they are written out so the whole contract reads in one place.  The timestep is the
    #: task's physics step (0.005 s, four per 20 ms control step), as FID-015 requires when the two are separated.
    fidelity = {
        "engine": "gymnasium:humanoidtoolbench/G1BallMove-L0-S",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "the upstream Task.reset(seed) seeds the layout randomizers (dr/manager.py:29-36), so one seed "
                     "and one action sequence repeat the upstream layout; this package's fake does not draw a layout "
                     "and its 43-joint state is deterministic, so the fake repeats for every seed.  The sim backend "
                     "was not run.",
        },
        "timestep_ms": 5.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "F0 is the claim of the fake backend: it is kinematic and sets each of the 43 joint positions to the "
            "commanded value; it models no rigid-body dynamics, contacts, actuator forces, sensors or noise.  The "
            "upstream simulation is MuJoCo rigid-body dynamics with contacts, but it was not run here.",
            "the fake omits the camera streams: the real observation adds head_stereo_left, head_stereo_right, "
            "wrist_left and wrist_right, each 640 by 360 by 3 uint8 (tasks/g1_toolbench_tabletop.py:38-41,86-120), "
            "and the real observation space declares them; the fake returns only the 43-value joint_qpos",
            "the fake does not model the task layout, object poses, tool selection, contact metrics, success or "
            "failure predicates or the reward: reset starts every joint at zero (the controller init_qpos), step "
            "returns reward 0.0 and never terminates on success; only the registered 3000-step truncation is applied",
            "the fake applies the action once per 20 ms control step, while the upstream applies it over 4 physics "
            "steps of 5 ms (tasks/g1_toolbench_tabletop.py:70-73, envs/sonic_loco_manip.py:70,78); timestep_ms names "
            "the 5 ms physics step as FID-015 requires when the two are separated, and a cap.world.step.v1 tick is "
            "one 20 ms control step",
            "no rendering: the fake render() returns no frames and cap.world.render.v1 stays unbound",
            "the fake does not reproduce the upstream numpy random stream or the layout draw; a seed gives the same "
            "zero joint state in the fake and a different layout upstream",
            "the sim backend was not run: it needs gymnasium, MuJoCo 3.11.0, torch 2.7.0, gear_sonic and "
            "decoupled-wbc (pyproject.toml:8-22), a GPU with EGL headless rendering (README.md:20-28), and a "
            "sonic_config from the evaluation CLI (cli/eval_decoupled_wbc.py:154-161) that the registration alone "
            "does not supply",
            "no wall-clock pacing: realtime_factor 0, so ticks advance simulated time only",
            "snapshot and restore are not offered: the environment exposes no get_state or set_state",
        ],
    }
