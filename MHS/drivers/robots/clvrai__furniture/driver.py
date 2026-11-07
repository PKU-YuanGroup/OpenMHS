"""OpenMHS driver for gh.clvrai/furniture: the IKEA furniture-assembly Gym environment (simulated, R0).

The card's entry symbol is ``furniture.env.furniture_gym:FurnitureGym``, the legacy Gym wrapper that constructs the
concrete environment with ``make_env(name, config)`` and exposes its ``observation_space`` and ``action_space``
(``furniture/env/furniture_gym.py:16-33``).  This package serves the registered ``IKEASawyer-v0`` environment
(``furniture/env/__init__.py:32-43``) as a ``GymnasiumDriver``: the bridge accepts both the gymnasium and the legacy
gym API, derives ``cap.world.step.v1`` from the action space (the wrapper's ``Dict`` with a ``default`` ``Box`` of
per-element bounds -1 to 1, ``furniture/env/furniture.py:294-310``) and reports the four-tuple step result as
``(observation, reward, terminated, truncated, info)`` (``furniture/env/furniture_gym.py:52-65``).  The device is
simulated (R0): there is no hardware backend, no e-stop path to a machine and no operator-required limit.

Why a package fake and not the upstream simulator: the clone needs Python 3.7, MuJoCo 2.0 and Unity 2018.4.23f1
(``docs/installation.md:3-7``), and package code never imports the clone.  The fake backend is a pure-Python F0
stand-in that mirrors the wrapper's public ``reset``, ``step`` and ``close``; it models the action and observation
shapes and a placeholder kinematic response, not MuJoCo contact, assembly, reward or rendering.  A backend name that
``backends`` does not list (``sim``) is served by ``gym.make("IKEASawyer-v0", unity=False)`` through
``GymnasiumDriver.open_native``; that path was not run here.

The ``fidelity`` attribute is the complete fidelity contract of the model as deployed (spec 05-fidelity FID-002).
Every constant and rule cites a line of the clone at the pinned commit ``ed4a905e7beb1daf3af7717d979e0ba93421077a``.
This package is model-authored and unreviewed: it is checked on the fake backend only.
"""

from mhs.driver import Fact, GymnasiumDriver

GYM = "furniture/env/furniture_gym.py"
ENV = "furniture/env/furniture.py"
SAWYER = "furniture/env/furniture_sawyer.py"
INIT = "furniture/env/__init__.py"
CONFIG = "furniture/config/furniture.py"
CHAIR = "furniture/env/models/assets/objects/swivel_chair_0700.xml"


class FurnitureAssembly(GymnasiumDriver):
    """The IKEASawyer-v0 environment behind the FurnitureGym wrapper, simulated on the package fake."""

    device_id = "ikea-furniture-sawyer"
    device_kind = "world.sim"
    resource_id = "world"
    mode, risk = "simulated", "R0"
    env_id = "IKEASawyer-v0"
    #: The sim path skips the Unity interface (config.unity defaults to True, furniture/config/furniture.py:20-23);
    #: the fake backend ignores this configuration.  The sim path was not run.
    env_kwargs = {"unity": False}
    native = "furniture.env.furniture_gym:FurnitureGym"
    backends = {"fake": ".fake:FakeFurnitureGym"}
    action_space_ref = f"{ENV}:298-310"
    fidelity_level = "F0"
    display_name = "IKEA Furniture Assembly IKEASawyer-v0 (Gym simulation, simulated)"
    vendor, model = "CLVR Lab, USC", "IKEASawyer-v0 / FurnitureGym"
    tags = ["ikea", "furniture-assembly", "sawyer", "gym", "mujoco", "manipulation",
            "reinforcement-learning", "simulation"]
    facts = [
        Fact("FurnitureGym is the Gym wrapper: its constructor builds the concrete environment with "
             "make_env(name, config) and copies the environment's observation_space and action_space",
             source="upstream_code", ref=f"{GYM}:16-33"),
        Fact("FurnitureGym.reset calls the wrapped environment's reset and returns the observation only, and "
             "FurnitureGym.step returns the wrapped (observation, reward, done, info) tuple",
             source="upstream_code", ref=f"{GYM}:52-65"),
        Fact("IKEASawyer-v0 is registered with entry_point furniture.env.furniture_gym:FurnitureGym and kwargs "
             "id IKEASawyer-v0, name FurnitureSawyerEnv, furniture_name swivel_chair_0700, background Industrial "
             "and port 1050", source="upstream_code", ref=f"{INIT}:32-43"),
        Fact("The action space is a Dict with one member named default, a Box of shape (dof,) bounded by "
             "low -1 and high 1 per element", source="upstream_code", ref=f"{ENV}:294-310"),
        Fact("For control_type ik the Sawyer dof is 3 + 3 + 1 + 1 for move, rotate, select and connect",
             source="upstream_code", ref=f"{SAWYER}:60-64"),
        Fact("When object_ob is enabled, object_ob is a Box of shape (3 + 4) * n_objects: position 3 and "
             "quaternion 4 per object", source="upstream_code", ref=f"{ENV}:230-237"),
        Fact("When robot_ob is enabled, the Sawyer ik observation space adds a Box of shape "
             "3 + 4 + 3 + 3 + 2 for pos, quat, velp, velr and gripper", source="upstream_code",
             ref=f"{SAWYER}:44-48"),
        Fact("object_ob, object_ob_all and robot_ob default to True", source="upstream_code",
             ref=f"{CONFIG}:230-246"),
        Fact("The swivel_chair_0700 furniture model declares three bodies: 1_chair_base, 2_chair_column and "
             "3_chair_seat", source="upstream_code", ref=f"{CHAIR}:19-47"),
        Fact("The furniture part count is len(self.mujoco_objects), the children of the loaded furniture XML",
             source="upstream_code", ref=f"{ENV}:2001-2002"),
        Fact("_get_obs concatenates each object's position and quaternion into object_ob", source="upstream_code",
             ref=f"{ENV}:1362-1379"),
        Fact("The Sawyer _get_obs builds robot_ob from gripper_qpos, eef_pos, eef_quat, eef_velp and eef_velr "
             "for a non-qpos observation", source="upstream_code", ref=f"{SAWYER}:103-153"),
        Fact("max_episode_steps defaults to 2000", source="upstream_code", ref=f"{CONFIG}:164-168"),
        Fact("_after_step marks the episode terminal when the episode length reaches max_episode_steps or the "
             "episode failed, and _step also marks success when all required parts are connected",
             source="upstream_code", ref=f"{ENV}:440-480"),
        Fact("The reward is success_reward + touch_reward + pick_reward + ctrl_penalty, and ctrl_penalty is "
             "-ctrl_penalty_coef times the sum of the squared actions", source="upstream_code",
             ref=f"{ENV}:524-550"),
        Fact("ctrl_penalty_coef defaults to 1e-3", source="upstream_code", ref=f"{CONFIG}:290-295"),
        Fact("control_freq defaults to 10", source="upstream_code", ref=f"{CONFIG}:72"),
        Fact("_do_simulation sets _model_timestep from sim.model.opt.timestep and _control_timestep from "
             "1.0 / control_freq, then runs int(control_timestep / model_timestep) physics steps per environment "
             "step", source="upstream_code", ref=f"{ENV}:2849-2881"),
        Fact("The environment seeds its numpy RandomState with config.seed at construction, and reset draws the "
             "furniture placement randomness from that generator", source="upstream_code", ref=f"{ENV}:72"),
        Fact("config.seed defaults to 123", source="upstream_code", ref=f"{CONFIG}:324"),
        Fact("When config.unity is set the environment creates a UnityInterface for rendering", source="upstream_code",
             ref=f"{ENV}:174-182"),
        Fact("The prerequisites are Python 3.7, MuJoCo 2.0 and Unity 2018.4.23f1", source="vendor_doc",
             ref="docs/installation.md:3-7"),
        Fact("setup.py install_requires lists gym, mujoco-py, numpy, scipy and the other upstream dependencies",
             source="upstream_code", ref="setup.py:11-31"),
    ]
    safe_state = ("the simulation stops advancing: no step or reset is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the environment state is kept and stays readable")
    #: FurnitureGym.reset takes no options either (furniture/env/furniture_gym.py:52-57), so the reset input the
    #: bridge serves is only the seed it records; `options` is left out of the schema and is refused.
    _RESET_INPUTS = {
        "seed": {"type": "integer", "minimum": 0,
                 "description": "Seed recorded in the receipt; FurnitureGym.reset takes no seed, so it does not "
                                "reseed the wrapped environment"},
    }
    #: The complete fidelity contract of the model as deployed (spec 05-fidelity FID-002).  The package runs only
    #: its F0 kinematic fake; the clone's MuJoCo/Unity environment is cited for provenance but was never opened here.
    fidelity = {
        "engine": "gym:IKEASawyer-v0",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "seeded",
            "seed_control": "none",
            "notes": "FurnitureGym.reset takes no seed (furniture/env/furniture_gym.py:52-57); the clone seeds its "
                     "numpy RandomState with config.seed only at construction (furniture/env/furniture.py:72, "
                     "default 123 at furniture/config/furniture.py:324), so cap.world.seed.v1 and the reset seed are "
                     "recorded by the bridge but cannot reseed the wrapped environment.  The fake starts from a fixed "
                     "placeholder state and repeats exactly, but it does not share a random stream with upstream.",
        },
        #: One environment step is one control period, 1 / control_freq = 0.1 s (furniture.py:2855).  The MuJoCo
        #: physics timestep is not stated in the clone (base.xml:4 sets only impratio and cone), so the physics
        #: timestep is not published here; the step runs int(control_timestep / model_timestep) physics steps
        #: (furniture.py:2878).
        "timestep_ms": 100.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "the package serves an F0 kinematic stand-in, not the MuJoCo furniture-assembly environment: no "
            "rigid-body dynamics, contacts, weld/equality constraints, inverse kinematics, gripper or furniture "
            "placement are modelled, and the assembly reward and success flag are not computed",
            "the fake returns the real low-dimensional observation lengths for the registered environment "
            "(object_ob 21 = (3 + 4) * 3 for the three swivel_chair_0700 bodies, robot_ob 15 = 3 + 4 + 3 + 3 + 2 "
            "for Sawyer ik) but every value is a placeholder; the camera_ob, depth_ob and segmentation_ob arrays "
            "are not returned because visual_ob defaults to False (furniture/config/furniture.py:248-252)",
            "the fake accepts only the registered environment's 8-element Sawyer ik action (3 + 3 + 1 + 1, "
            "furniture_sawyer.py:60-64); the other agents, control types and action sizes are not served",
            "the seed of cap.world.reset/cap.world.seed does not reach the wrapper: FurnitureGym.reset takes no "
            "seed (furniture_gym.py:52-57), so determinism.seed_control is 'none'",
            "one cap.world.step.v1 tick is one environment step (one control period of 100 ms from control_freq 10, "
            "furniture/config/furniture.py:72 and furniture.py:2855); the MuJoCo physics timestep and the number of "
            "physics iterations per control step are not stated in the clone (base.xml:4), so only the control "
            "period is published",
            "the wrapper's step returns a four-tuple and reports done as terminated (furniture/env/furniture_gym.py:"
            "59-65); the fake reaches done only at the 2000-step horizon and never succeeds",
            "no wall-clock pacing: realtime_factor 0, only commands advance the state",
            "snapshot_restore is false: FurnitureGym exposes get_env_state but no set_state/get_state pair for the "
            "Gymnasium bridge",
            "no Unity rendering and no MuJoCo viewer: the package exposes no cap.world.render.v1 and the "
            "UnityInterface path (furniture/env/furniture.py:174-182) was not run",
            "the upstream MuJoCo/Unity stack was never installed or opened where the gate ran, so no trajectory was "
            "compared with it; no physical device is modelled and nothing was validated against hardware",
        ],
    }
