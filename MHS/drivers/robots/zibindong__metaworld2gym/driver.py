"""OpenMHS driver for gh.zibindong/metaworld2gym: the Meta-World gym wrapper (simulated, R0).

DEVIATION FROM THE CARD: the card proposes the ``MujocoDriver`` family helper because the repository vendors the
Meta-World MuJoCo assets, but the card's first confirmed entry symbol is a Gymnasium-style wrapper around a Meta-World
task (``metaworld2gym/metaworld_env.py:93``), not one raw MJCF file.  ``MetaWorldEnv.reset()`` returns a dictionary of
observations and ``MetaWorldEnv.step(action)`` returns ``(observation, reward, done, info)`` with a four-element
normalised action (``metaworld2gym/metaworld_env.py:295-308``); a ``MujocoDriver`` serves one MJCF model through
``model_path``/``mj_step`` and cannot express that task-level interface.  The package is therefore a ``GymnasiumDriver``
(which accepts both gymnasium and the legacy ``gym`` API, ``mhs/bridge/gymnasium.py``) over
``metaworld2gym.metaworld_env:MetaWorldEnv`` and binds the card's ``cap.world.step.v1`` and ``cap.world.reset.v1``.
The wrapper is task-parameterised; this package names the assembly task (``assembly-v2-goal-observable``), whose v1
class is one of the card's entry symbols and whose scene is the card's first model.

The wrapper builds ``metaworld.envs.ALL_V2_ENVIRONMENTS_GOAL_OBSERVABLE[task_name]()``
(``metaworld2gym/metaworld_env.py:135-138``) and its default observation dictionary is
``image``, ``depth``, ``agent_pos``, ``point_cloud`` and ``full_state`` (``metaworld2gym/metaworld_env.py:121-127``).
The bridge derives ``cap.world.step.v1``'s action object from the wrapped environment's four-element ``Box``
(``-1 .. +1``, ``metaworld/envs/mujoco/sawyer_xyz/sawyer_xyz_env.py:128-131``), so out-of-range action elements are
refused by the runtime before the fake is called.

The upstream packages (gym, mujoco-py, torch, numpy) are not installed where the gate runs
(``setup.py:9-16``) and package code never imports the clone.  The ``fake`` backend is this package's pure-Python
stand-in (``fake.py``); no ``sim`` backend is declared, because the wrapper is not registered with ``gym.make`` and
this package never ran the upstream MuJoCo stack.  The device is simulated (R0): there is no hardware backend and no
operator-required limit.  This package is model-authored and unreviewed; it is checked on the fake backend only.
"""

from mhs.driver import Fact, GymnasiumDriver

ENV = "metaworld2gym/metaworld_env.py"
BASE = "metaworld/envs/mujoco/sawyer_xyz/sawyer_xyz_env.py"
SCENE = "metaworld/envs/assets_v2/scene/basic_scene.xml"
MUJOCO_ENV = "metaworld/envs/mujoco/mujoco_env.py"


class MetaWorld2GymAssembly(GymnasiumDriver):
    """The Meta-World assembly task through the metaworld2gym wrapper, simulated on the package fake."""

    device_id = "metaworld2gym-assembly"
    device_kind = "world.sim"
    resource_id = "world"
    mode, risk = "simulated", "R0"
    native = "metaworld2gym.metaworld_env:MetaWorldEnv"
    backends = {"fake": ".fake:FakeMetaWorldEnv"}
    action_space_ref = f"{BASE}:128-131"
    display_name = "Meta-World assembly through the metaworld2gym wrapper (simulated)"
    vendor, model = "Zibin Dong", "metaworld2gym MetaWorldEnv / assembly-v2-goal-observable"
    tags = ["metaworld", "metaworld2gym", "assembly", "mujoco", "manipulation", "simulation", "gym"]
    facts = [
        Fact("The repository contains a gym wrapper and an automatic demonstration-collection script for Meta-World",
             source="vendor_doc", ref="README.md:3"),
        Fact("The README creates an environment with metaworld2gym.make(\"door-open\"), calls reset() and step(), and "
             "unpacks the step result as next_obs, reward, done, info", source="vendor_doc",
             ref="README.md:30-33"),
        Fact("The default observation dictionary is image (3, 224, 224), depth (224, 224), point_cloud (1024, 6), "
             "agent_pos (9,) and full_state (39,)", source="vendor_doc", ref="README.md:39-43"),
        Fact("MetaWorldEnv defaults observation_meta to image, depth, agent_pos, point_cloud and full_state",
             source="upstream_code", ref=f"{ENV}:121-127"),
        Fact("MetaWorldEnv appends -v2-goal-observable to a task name and builds that class from "
             "metaworld.envs.ALL_V2_ENVIRONMENTS_GOAL_OBSERVABLE", source="upstream_code", ref=f"{ENV}:135-138"),
        Fact("MetaWorldEnv sets the episode length to 200 steps and takes its action_space from the wrapped "
             "Meta-World environment", source="upstream_code", ref=f"{ENV}:207-208"),
        Fact("MetaWorldEnv.step returns (observation dictionary, reward, done, info) and forces done at the 200-step "
             "episode length", source="upstream_code", ref=f"{ENV}:295-300"),
        Fact("MetaWorldEnv.reset resets the wrapped environment and returns the observation dictionary",
             source="upstream_code", ref=f"{ENV}:302-308"),
        Fact("The wrapped Meta-World environment's action space is a four-element Box from -1 to +1",
             source="upstream_code", ref=f"{BASE}:128-131"),
        Fact("SawyerXYZEnv.step applies the first three action elements through set_xyz_action and the last element "
             "through do_simulation", source="upstream_code", ref=f"{BASE}:406-408"),
        Fact("SawyerXYZEnv defaults frame_skip to 5 and action_scale to 1/100", source="upstream_code",
             ref=f"{BASE}:93-98"),
        Fact("The MJCF basic scene sets the physics timestep to 0.0025 s", source="upstream_code", ref=f"{SCENE}:2"),
        Fact("The base environment's dt is model.opt.timestep multiplied by frame_skip", source="upstream_code",
             ref=f"{MUJOCO_ENV}:104-106"),
        Fact("The package requires gym>=0.15.4, mujoco-py>=2.0,<2.2, numpy>=1.18, torch, termcolor, zarr and numba",
             source="upstream_code", ref="setup.py:9-16"),
    ]
    safe_state = ("the simulation stops advancing: no step or reset is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the last observation stays readable")
    #: The complete fidelity contract of what this package serves (spec 05-fidelity FID-002).  The model as deployed
    #: is the package's kinematic F0 fake: the MuJoCo scene is cited for provenance, but this package declares no
    #: backend that runs it.  The bridge derives engine, determinism, timestep and clock; they are written out here
    #: so the whole contract reads in one place.
    fidelity = {
        "engine": "metaworld2gym:MetaWorldEnv/assembly-v2-goal-observable",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "seeded",
            "seed_control": "none",
            "notes": "MetaWorldEnv.reset takes no seed argument and calls the wrapped environment's reset "
                     "(metaworld2gym/metaworld_env.py:302-308); the wrapped v2 environment samples its reset vector "
                     "from numpy's generator, so the seed of cap.world.reset/cap.world.seed is recorded by the bridge "
                     "but cannot reseed the upstream environment.  The fake uses a fixed placeholder start state and "
                     "repeats exactly, but it does not share a random stream with upstream.",
        },
        "timestep_ms": 2.5,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "the package serves an F0 kinematic stand-in, not the MuJoCo scene: contacts, rigid-body dynamics, the "
            "gripper, object motion and the reward of the assembly task are not modelled; the upstream MuJoCo stack "
            "was never installed or run, so no trajectory was compared with it",
            "the fake keeps the wrapper's default observation keys but returns smaller placeholder arrays: image "
            "3x8x8, depth 8x8 and point_cloud 16x6, where the configured device renders 3x224x224, 224x224 and "
            "1024x6 (README.md:39-43); agent_pos stays 9 and full_state stays 39",
            "there is no rendering, camera, depth sensor or point-cloud generator in the fake; the image, depth and "
            "point-cloud values are test data",
            "the seed of cap.world.reset/cap.world.seed does not reach the wrapped environment: MetaWorldEnv.reset "
            "takes no seed (metaworld2gym/metaworld_env.py:302-308), so determinism.seed_control is 'none'",
            "the wrapper's step returns a four-tuple and forces done at 200 steps (metaworld2gym/metaworld_env.py:"
            "207, :299); the bridge reports that done flag as terminated, not truncated",
            "timestep_ms is the MJCF physics step of 2.5 ms (metaworld/envs/assets_v2/scene/basic_scene.xml:2); one "
            "cap.world.step.v1 tick is one wrapper step and advances frame_skip=5 physics frames, a 12.5 ms control "
            "period (metaworld/envs/mujoco/sawyer_xyz/sawyer_xyz_env.py:93-98)",
            "no wall-clock pacing: realtime_factor 0, only commands advance simulated time",
            "snapshot_restore is false: the wrapper exposes no get_state/set_state pair (the wrapped environment has "
            "get_env_state/set_env_state, which the Gymnasium bridge does not snapshot)",
            "no physical device is modelled and nothing was validated against hardware",
        ],
    }
