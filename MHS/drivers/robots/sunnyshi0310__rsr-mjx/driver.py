"""OpenMHS driver for gh.sunnyshi0310/rsr-mjx: the Unitree Go2 flat-terrain MJCF scene (a MuJoCo family driver).

A ``MujocoDriver`` is configuration only: ``model_path`` names the MJCF scene and the bridge derives the contract from
the model it loads.  ``cap.world.step.v1`` takes ``{ticks, action: {ctrl: [...]}}``; each of the twelve ``ctrl``
elements is checked against the model's ``actuator_ctrlrange`` before it is written to ``data.ctrl``, then ``mj_step``
runs ``ticks`` times.  ``cap.world.reset.v1`` restores the model defaults with ``mj_resetData`` + ``mj_forward``.  The
world state is the bridge's integration state (``time_ms``, ``qpos``, ``qvel``, ``ctrl``, ``tick``, ``timestep_ms``,
``seed``).  The device is simulated (R0): there is no hardware backend, no e-stop path to a machine and no
operator-required bound; the control envelope is the model's own.

The repository calls itself an RSR (Real-to-Sim-to-Real) reinforcement-learning framework built on MuJoCo MJX and Brax
(README.md:3).  The card's entry ``Joystick`` is the Go2 joystick task: it defaults to ``task="flat_terrain"``
(joystick.py:83-87) and ``task_to_xml`` maps that task to ``scene_mjx_feetonly_flat_terrain.xml``
(go2_constants.py:5-19), the scene the registry's ``Go2JoystickFlatTerrain`` entry builds (locomotion/__init__.py:16-22).
This package serves that scene, the card's ``models[1]``.  The registry's environment object itself is an MJX/Brax
``MjxEnv`` whose ``step`` takes a normalized action and returns an ``mjx_env.State``; the SDK has no MJX family and jax
and mujoco-mjx are not installed here, so the package serves the MuJoCo model underneath it as a ``MujocoDriver``
(raw ``data.ctrl``, the card's candidate classes ``cap.world.step.v1`` and ``cap.world.reset.v1``).  The environment's
action mapping, command sampling, reward, observation vector and fall termination are not served; the fidelity gaps
say so.

MuJoCo is not installed where the gate runs (no network, no pip), so ``backends["fake"]`` is this package's stand-in
``mujoco`` module (fake.py).  It reads the same scene and its include for the joint layout, the actuator control
ranges the compiler would inherit from the joint ranges, and the 4 ms option timestep, but its integration is a
placeholder, not MuJoCo's physics.  The fake fidelity contract is F0 for that reason; a backend name ``backends`` does
not list (``sim``) imports the real ``mujoco`` module and loads the same scene as F1, which was not run here.  This
package is model-authored and unreviewed: it is checked on the fake backend only.
"""

from mhs.driver import Fact, MujocoDriver

from .fake import FakeMujoco

#: The card's models[1], relative to this package directory: the read-only clone under robots/ at the pinned commit.
SCENE = "ppo_train/go2_training/mujoco_playground/_src/locomotion/go2/xmls/scene_mjx_feetonly_flat_terrain.xml"
MODEL = "ppo_train/go2_training/mujoco_playground/_src/locomotion/go2/xmls/go2_mjx_feetonly.xml"
CONSTANTS = "ppo_train/go2_training/mujoco_playground/_src/locomotion/go2/go2_constants.py"
JOYSTICK = "ppo_train/go2_training/mujoco_playground/_src/locomotion/go2/joystick.py"
LOCOMOTION = "ppo_train/go2_training/mujoco_playground/_src/locomotion/__init__.py"
MODEL_PATH = "../../../../robots/sunnyshi0310/rsr-mjx/" + SCENE


class Go2FlatTerrain(MujocoDriver):
    device_id = "go2-flat-terrain"
    model_path = MODEL_PATH
    backends = {"fake": FakeMujoco}
    display_name = "Unitree Go2 flat-terrain MJCF scene (RSR-MJX)"
    vendor, model = "sunnyshi0310", "rsr-mjx Go2 feetonly flat terrain"
    tags = ["go2", "unitree", "quadruped", "joystick", "mujoco", "mjx", "simulation", "rsr"]
    facts = [
        Fact("The project calls itself an RSR (Real-to-Sim-to-Real) reinforcement-learning framework built on MuJoCo "
             "MJX and Brax", source="vendor_doc", ref="README.md:3"),
        Fact("The two experimental platforms are an Airbot Play arm and a Unitree Go2 quadruped trained for "
             "flat/rough terrain joystick control", source="vendor_doc", ref="README.md:9-10"),
        Fact("Go2 training scripts need PYTHONPATH=ppo_train/go2_training and the Go2 assets are bundled under "
             "mujoco_playground/_src/locomotion/go2/xmls", source="vendor_doc", ref="README.md:67-68"),
        Fact("The card's entry Joystick is the Go2 joystick task and its default task is flat_terrain",
             source="upstream_code", ref=f"{JOYSTICK}:83-87"),
        Fact("The registry's Go2JoystickFlatTerrain entry is Joystick with task=flat_terrain",
             source="upstream_code", ref=f"{LOCOMOTION}:16-22"),
        Fact("task_to_xml maps flat_terrain to scene_mjx_feetonly_flat_terrain.xml and rough_terrain to "
             "scene_mjx_feetonly_rough_terrain.xml", source="upstream_code", ref=f"{CONSTANTS}:5-19"),
        Fact("The served scene is the MuJoCo model 'go2 feetonly flat terrain scene' and it includes "
             "go2_mjx_feetonly.xml", source="upstream_code", ref=f"{SCENE}:1-2"),
        Fact("The model compiler declares radian angles, a mesh directory, and autolimits enabled",
             source="upstream_code", ref=f"{MODEL}:2"),
        Fact("The model integrates with Euler at a 0.004 s timestep",
             source="upstream_code", ref=f"{MODEL}:4"),
        Fact("The go2 default class gives its position actuators inheritrange 1 and forcerange -24 to 24; the knee "
             "class overrides the force range to -35.55 to 35.55", source="upstream_code", ref=f"{MODEL}:9-24"),
        Fact("The abduction joints have range -1.0472 to 1.0472 rad, the hip (thigh) joints -1.5708 to 3.4907 rad and "
             "the knee (calf) joints -2.7227 to -0.83776 rad", source="upstream_code", ref=f"{MODEL}:15-24"),
        Fact("The actuator block declares twelve position actuators, one per Go2 leg joint: four abduction (hip), "
             "four hip (thigh) and four knee (calf) channels", source="upstream_code", ref=f"{MODEL}:191-204"),
        Fact("Joystick initializes _init_q and _default_pose from the home keyframe's qpos",
             source="upstream_code", ref=f"{JOYSTICK}:98-99"),
        Fact("Joystick.reset starts from _init_q, then draws a base x/y offset from -0.5 to 0.5, a yaw "
             "from -3.14 to 3.14 rad and a base velocity from -0.5 to 0.5", source="upstream_code",
             ref=f"{JOYSTICK}:123-138"),
        Fact("The joystick default config sets action_scale 0.5, ctrl_dt 0.02 s and sim_dt 0.004 s",
             source="upstream_code", ref=f"{JOYSTICK}:13-21"),
        Fact("Joystick.step selects actual_action from the delay buffer when enabled, otherwise from the input, "
             "and sets motor_targets to _default_pose plus actual_action times action_scale",
             source="upstream_code", ref=f"{JOYSTICK}:207-216"),
        Fact("The joystick episode terminates when the IMU up vector's vertical component falls below zero",
             source="upstream_code", ref=f"{JOYSTICK}:281-283"),
        Fact("The scene's home keyframe sets the nominal qpos and ctrl of the standing pose",
             source="upstream_code", ref=f"{SCENE}:27-35"),
    ]
    safe_state = ("the simulation stops advancing: no step or reset is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the integration state is kept and stays readable")
    #: The fake contract (F0: the stand-in models no dynamics).  A real MuJoCo backend would be F1; see
    #: ``fidelity_by_backend["sim"]``.  The bridge derives the engine, timestep, determinism and clock; they are
    #: written out so the whole contract reads in one place.
    fidelity = {
        "engine": "mujoco:go2 feetonly flat terrain scene",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "none",
            "seed_control": "none",
            "notes": "The fake is a deterministic placeholder integrator, but no trajectory was compared with "
                     "MuJoCo or with the upstream MJX environment and the bridge's reset takes no seed (it "
                     "restores the model defaults), so no seed controls a trajectory. The bridge derives no "
                     "determinism claim.",
        },
        "timestep_ms": 4.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": True,
        "gaps": [
            "the fake backend is a stand-in for the mujoco library, not MuJoCo: it parses the scene and its include "
            "for the joint layout, the actuator control ranges inherited from the joint ranges and the 4 ms option "
            "timestep, but integrates a placeholder first-order motion of each actuated hinge; it loads no mesh or "
            "texture and resolves no contact, friction, gravity, inertia, actuator force, sensor or constraint",
            "the served device is the raw MJCF scene, not the Joystick MjxEnv: the environment's normalized action "
            "(home pose + action_scale * action), command sampling, reward terms, observation vector, delay buffers, "
            "domain randomization and fall termination are not exposed by the MuJoCo family",
            "the bridge resets with mj_resetData to the model defaults, while Joystick.reset starts from the home "
            "keyframe and randomizes the base x/y, yaw and velocity; this driver does not reproduce the environment "
            "reset",
            "the environment advances 0.02 s of control time per action (ctrl_dt) in 0.004 s simulation steps "
            "(sim_dt); the bridge advances only the model's 0.004 s step per tick",
            "MuJoCo, mujoco-mjx and jax are not installed where the gate ran and cannot be installed there (no "
            "network, no pip); no trajectory of this package was compared with the real engine or the upstream "
            "environment, and the sim backend was not run",
            "only the card's models[1] flat-terrain scene is served; the bowl, rough-terrain, stairs and "
            "full-collision scenes are other models and are not part of this driver",
            "no physical Unitree Go2 is modelled and nothing was validated against hardware",
        ],
    }
    #: The contract a real MuJoCo engine would have on this same scene; it was not run here.
    fidelity_by_backend = {
        "sim": {
            "engine": "mujoco:go2 feetonly flat terrain scene",
            "fidelity_level": "F1",
            "gaps": [
                "the served device is the raw MJCF scene, not the Joystick MjxEnv: the environment's normalized "
                "action, command sampling, reward, observation vector and fall termination are not served",
                "the bridge resets with mj_resetData to the model defaults, while Joystick.reset starts from the "
                "home keyframe and randomizes the base pose and velocity",
                "the environment advances 0.02 s of control time per action in 0.004 s simulation steps; the bridge "
                "advances only the model's 0.004 s step per tick",
                "the model is read from the read-only clone in place; no mesh, contact or actuator parameter was "
                "checked against a physical Go2 and no trajectory was compared with the upstream MJX environment",
                "only the card's models[1] flat-terrain scene is served; the other scenes are other models",
            ],
        },
    }
