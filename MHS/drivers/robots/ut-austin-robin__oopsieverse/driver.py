"""OpenMHS driver for gh.ut-austin-robin/oopsieverse: the DamageableCloseDrawer RoboCasa environment.

OopsieVerse is a damage-aware, simulator-agnostic benchmark for robot manipulation (README.md:10) whose RoboCasa
half runs on Robosuite and MuJoCo (docs/oopsiebench.md:3).  The card's ``family-config`` / ``GymnasiumDriver``
decision fits the confirmed entry class: ``DamageableCloseDrawer`` is a Gymnasium-shaped environment whose
``reset`` returns ``(observation, info)`` and whose ``step`` returns ``(observation, reward, done, info)``
(``damagesim/robosuite/damageable_env.py:382-409``).  ``env_id`` is the OopsieVerse ``EnvironmentRegistry`` name
(``oopsiebench/envs/registry.py:65``); the clone does not register it with gymnasium.

The device is simulated (R0): there is no hardware backend, no native stop and no operator-required limit.  A
backend name that ``backends`` does not list (``sim``) would be served by ``gymnasium.make(env_id)``
(``GymnasiumDriver.open_native``), but that path needs RoboCasa, Robosuite, MuJoCo and gymnasium and is not run
here; the gate checks the package's pure Python fake only (``fake.py``).

The ``fidelity`` contract below states the model as deployed: RoboCasa on Robosuite/MuJoCo at 20 control Hz
(``oopsiebench/envs/registry.py:20-21``), with the fake's reductions and the un-run sim path in ``gaps``.  This
package is model-authored and unreviewed; it is checked on the fake backend only and no hardware or upstream run
was made.
"""

from mhs.driver import Fact, GymnasiumDriver

REGISTRY = "oopsiebench/envs/registry.py"
CLOSE_DRAWER = "oopsiebench/envs/robocasa/close_drawer.py"
DAMAGEABLE = "damagesim/robosuite/damageable_env.py"
CORE = "damagesim/core/damageable_env.py"
TEST = "scripts/tests/test_robocasa.py"
TELEOP = "scripts/teleop_robocasa.py"


class OopsieVerseCloseDrawer(GymnasiumDriver):
    device_id = "oopsieverse-close-drawer"
    #: The OopsieVerse EnvironmentRegistry key, not a gymnasium registration.
    env_id = "close_drawer"
    native = "oopsiebench.envs.robocasa.close_drawer:DamageableCloseDrawer"
    backends = {"fake": ".fake:FakeCloseDrawerEnv"}
    display_name = "OopsieVerse DamageableCloseDrawer (RoboCasa / MuJoCo)"
    vendor, model = "UT Austin RobIn", "close_drawer"
    mode = "simulated"
    risk = "R0"
    tags = ["oopsieverse", "robocasa", "robosuite", "mujoco", "damage", "manipulation", "simulation", "gymnasium"]
    facts = [
        Fact("OopsieVerse is a damage-aware, simulator-agnostic framework and benchmark for learning and evaluating "
             "safer robot manipulation", source="vendor_doc", ref="README.md:10"),
        Fact("OopsieVerse builds on BEHAVIOR-1K/OmniGibson, RoboCasa and RoboSuite", source="vendor_doc",
             ref="README.md:38"),
        Fact("OopsieBench spans OmniGibson (NVIDIA Omniverse) and Robosuite (MuJoCo)", source="vendor_doc",
             ref="docs/oopsiebench.md:3"),
        Fact("The environment registry's default robot is PandaOmron and its default control frequency is 20",
             source="upstream_code", ref=f"{REGISTRY}:20-21"),
        Fact("close_drawer is registered with environment class CloseDrawer and damageable class "
             "DamageableCloseDrawer", source="upstream_code", ref=f"{REGISTRY}:65"),
        Fact("DamageableCloseDrawer constructs the environment with task_name close_drawer", source="upstream_code",
             ref=f"{CLOSE_DRAWER}:152-156"),
        Fact("CloseDrawer sets randomize_scene to True, so the scene is randomized per episode",
             source="upstream_code", ref=f"{CLOSE_DRAWER}:31-35"),
        Fact("The drawer starts with a door state between 0.95 and 1.0", source="upstream_code",
             ref=f"{CLOSE_DRAWER}:87-89"),
        Fact("The close_drawer episode starts with the drawer open", source="vendor_doc",
             ref="docs/oopsiebench.md:41"),
        Fact("CloseDrawer computes the reward as 10.0 times one minus the mean door state", source="upstream_code",
             ref=f"{CLOSE_DRAWER}:123-129"),
        Fact("The success check rejects the episode while any drawer joint position is above 0.05",
             source="upstream_code", ref=f"{CLOSE_DRAWER}:131-136"),
        Fact("The success check uses a gripper-to-drawer-root-body distance threshold of 0.75 m",
             source="upstream_code", ref=f"{CLOSE_DRAWER}:19-21"),
        Fact("The damageable environment reset returns (observation, info) and reinitializes damage tracking",
             source="upstream_code", ref=f"{DAMAGEABLE}:382-398"),
        Fact("The damageable environment step returns (observation, reward, done, info)", source="upstream_code",
             ref=f"{DAMAGEABLE}:400-409"),
        Fact("The observation appends a float32 health array", source="upstream_code", ref=f"{CORE}:259-269"),
        Fact("The proprio vector concatenates 7 joint sines, 7 joint cosines, 3 end-effector positions, 4 quaternion "
             "values and 2 gripper positions when those keys are present", source="upstream_code",
             ref=f"{DAMAGEABLE}:289-301"),
        Fact("The tests build the environment from the registry robot and a composite controller, with camera "
             "observations off and the registry control frequency", source="upstream_code", ref=f"{TEST}:49-59"),
        Fact("The teleoperation loop builds the environment action with robot.create_action_vector and steps the "
             "environment with the concatenated result", source="upstream_code", ref=f"{TELEOP}:838-845"),
        Fact("Installation clones RoboSuite and RoboCasa and pip-installs both", source="upstream_code",
             ref="install.py:130-150"),
        Fact("The package's declared dependencies are open3d, matplotlib, scipy, tyro, tqdm and numba",
             source="upstream_code", ref="pyproject.toml:17-25"),
    ]
    safe_state = ("the simulation stops advancing: the runtime refuses step and reset after an e-stop until "
                  "mhs.safety.reset clears the latch, and the last world state stays readable")
    #: The fidelity contract of the model as deployed (spec 05-fidelity section 2).  The bridge derives the engine
    #: prefix and the lockstep clock; the values are written out so the whole contract reads in one place.
    fidelity = {
        "engine": "gymnasium:close_drawer on RoboCasa/Robosuite (MuJoCo)",
        "fidelity_level": "F1",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "the fake re-seeds Python's random generator on reset(seed) and on cap.world.seed.v1; the "
                     "upstream damageable reset() takes no seed argument (damagesim/robosuite/damageable_env.py:382) "
                     "and the clone defines no seed setter, so a real sim deployment would ignore the seed and was "
                     "not run",
        },
        "timestep_ms": 50.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "the upstream model is RoboCasa on Robosuite/MuJoCo (docs/oopsiebench.md:3) with rigid-body dynamics and "
            "contacts; the fake is an analytic stand-in that models no contacts, friction, actuators, sensors or "
            "noise",
            "the fake's seven-value action vector is placeholder test data; the real PandaOmron composite-controller "
            "action is assembled at run time (scripts/teleop_robocasa.py:838-845) and its size and bounds are not "
            "stated in the clone, so the fake serves an unbounded action space",
            "the fake returns a reduced observation (robot0_eef_pos 3, robot0_gripper_qpos 2, robot0_proprio 23 and "
            "one health value); the upstream observation also carries the Robosuite observation keys and a health "
            "vector whose length is the number of tracked links (damagesim/core/damageable_env.py:259-269), which "
            "is not stated in the clone",
            "no cameras, depth, segmentation or rendering: the upstream test and teleoperation entry points used "
            "here set use_camera_obs=False (scripts/tests/test_robocasa.py:54-57, "
            "scripts/teleop_robocasa.py:1006-1007)",
            "no snapshot or restore: the clone defines no get_state/set_state on the environment",
            "the fake seeds its own generator; the upstream reset() takes no seed "
            "(damagesim/robosuite/damageable_env.py:382), so the sim backend would ignore cap.world.seed.v1 and "
            "the reset seed",
            "the sim backend was not run: close_drawer is registered in the clone's own EnvironmentRegistry "
            "(oopsiebench/envs/registry.py:65) and not with gymnasium.register, so gymnasium.make('close_drawer') is "
            "not provided; a real deployment needs an EnvironmentRegistry factory",
            "the fake's end-effector gain, door travel, start pose and health damage rate are placeholders, and the "
            "gripper-distance half of _check_success (close_drawer.py:138-142) is not modelled",
            "no physical device is modelled and nothing was validated against hardware; the fake was not compared "
            "with a RoboCasa run",
        ],
    }
