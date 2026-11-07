"""OpenMHS driver for gh.leesweqq/drl_peg-in-hole_ur5: the PyBullet UR5 peg-in-hole task as a Gymnasium family driver.

``PegInHoleGymEnv`` is a plain ``gymnasium.Env`` (rlenv.py:13): ``reset(seed=None, options=None)`` returns
``(observation, {})`` (rlenv.py:97-117), ``step(action)`` returns ``(observation, reward, done, truncated, info)``
(rlenv.py:142-177), and ``close()`` disconnects the PyBullet client (rlenv.py:267-268).  A ``GymnasiumDriver`` is
configuration only: the bridge derives the whole contract from the environment's spaces.  ``cap.world.step.v1`` takes
``{ticks, action}`` with the action ``{"values": [dx, dy, dz]}`` bounded by ``Box(-0.005, 0.005, (3,))``
(rlenv.py:43); ``cap.world.reset.v1`` takes ``{seed, options}`` and ``cap.world.seed.v1`` ``{seed}``.

The device is simulated (R0): there is no hardware backend, no e-stop path to a machine and no operator-required
limit.  The gate cannot import the upstream environment (it needs pybullet and the clone's URDF files, and package
code never imports the clone), so the ``fake`` backend is this package's own pure Python kinematic stand-in; it is not
the PyBullet environment and was not compared with one (see fake.py and the fidelity ``gaps``).  This package is
model-authored and unreviewed: it is checked on the fake backend only.
"""

from mhs.driver import Fact, GymnasiumDriver

RLENV = "rlenv.py"


class PegInHole(GymnasiumDriver):
    device_id = "peg-in-hole"
    native = "rlenv:PegInHoleGymEnv"
    backends = {"fake": ".fake:FakePegInHoleEnv"}
    action_space_ref = f"{RLENV}:43"
    display_name = "PyBullet UR5 peg-in-hole Gymnasium environment"
    vendor, model = "leesweqq", "drl_peg-in-hole_ur5"
    tags = ["peg-in-hole", "ur5", "pybullet", "reinforcement-learning", "simulation", "gymnasium"]
    facts = [
        Fact("The environment is PegInHoleGymEnv(gym.Env) and its constructor connects a PyBullet GUI client",
             source="upstream_code", ref=f"{RLENV}:13-16"),
        Fact("The observation space is a Dict with one Box field cam_image of shape (100, 100, 1), values 0 to 255, "
             "dtype uint8", source="upstream_code", ref=f"{RLENV}:32-40"),
        Fact("The camera image is 100 by 100 pixels", source="upstream_code", ref=f"{RLENV}:22-23"),
        Fact("The action space is a Box of three elements, each from -0.005 to 0.005",
             source="upstream_code", ref=f"{RLENV}:42-43"),
        Fact("reset has the signature reset(self, seed=None, options=None) and draws the hole position with "
             "random.uniform from the module-level random generator", source="upstream_code",
             ref=f"{RLENV}:97-113"),
        Fact("reset draws the hole position x from uniform(0.5, 0.6), y from uniform(0, 0.1) at z = 0.65",
             source="upstream_code", ref=f"{RLENV}:110-114"),
        Fact("The rest poses are [0, -1.57, 1.57, -1.5, -1.57, 0.0] and reset applies them, then steps the "
             "simulation 100 times", source="upstream_code", ref=f"{RLENV}:90-104"),
        Fact("step increments the step counter, clips the action to the action-space bounds and moves the end "
             "effector by the action offset", source="upstream_code", ref=f"{RLENV}:142-153"),
        Fact("step advances the PyBullet simulation 10 times after the motion command",
             source="upstream_code", ref=f"{RLENV}:154"),
        Fact("The maximum episode length is max_steps = 500", source="upstream_code", ref=f"{RLENV}:25"),
        Fact("An episode is truncated when the step counter reaches max_steps",
             source="upstream_code", ref=f"{RLENV}:175"),
        Fact("The reward is 10 * (-dist_xy - 0.5 * dist_z) plus 100 on insertion",
             source="upstream_code", ref=f"{RLENV}:240-249"),
        Fact("Insertion succeeds when the end effector is within 0.01 of the hole in the XY plane and within 0.1 "
             "in Z", source="upstream_code", ref=f"{RLENV}:257-262"),
        Fact("Collision is suppressed when the end effector is within 0.02 in XY and 0.15 in Z of the hole; "
             "otherwise contact with the table or the hole ends the episode",
             source="upstream_code", ref=f"{RLENV}:179-191"),
        Fact("step returns the five-tuple (observation, reward, done, truncated, info) and info reports "
             "insertion_success", source="upstream_code", ref=f"{RLENV}:142-177"),
        Fact("The camera projection uses a 60 degree field of view, near 0.01 and far 3.0",
             source="upstream_code", ref=f"{RLENV}:222-227"),
        Fact("close disconnects the PyBullet client", source="upstream_code", ref=f"{RLENV}:267-268"),
        Fact("The project is a DRL environment built with PyBullet and Gymnasium that simulates a UR5 peg-in-hole "
             "insertion task", source="vendor_doc", ref="README.md:5"),
        Fact("The camera captures 100x100 grayscale images as the visual observation",
             source="vendor_doc", ref="README.md:7"),
        Fact("The README's main installation line installs pybullet, gymnasium, stable-baselines3, matplotlib and "
             "pandas", source="vendor_doc", ref="README.md:81"),
    ]
    safe_state = ("the simulation stops advancing: no step or reset is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the environment state is kept and stays readable")
    #: The fidelity contract of the model as deployed (spec 05-fidelity section 2).  The bridge derives the engine,
    #: the determinism kind and the lockstep clock; they are written out so the whole contract reads in one place.
    #: The deployed model on the only declared backend is the package's kinematic fake, so the level is F0.
    fidelity = {
        "engine": "analytic:rlenv.PegInHoleGymEnv (package fake backend)",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "the package fake seeds its own target draw from reset(seed), so a fresh world repeats for one "
                     "seed and action sequence; upstream reset accepts seed but draws the hole from the module-level "
                     "random generator (rlenv.py:97-113) and its PyBullet client is not seeded, so seeded replay is a "
                     "property of the fake only",
        },
        "timestep_ms": 0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "kinematic stand-in only: the fake moves the end effector by the action offset and models no rigid-body "
            "dynamics, inverse kinematics, joint limits, gravity or contacts, so fidelity_level is F0 even though "
            "upstream runs PyBullet (rlenv.py:16-20, 119-132)",
            "contacts with the table and the hole are not modelled: the upstream collision test that terminates an "
            "episode (rlenv.py:179-191) is not reproduced, so episodes end only on insertion or the 500-step "
            "truncation (rlenv.py:175)",
            "the grayscale camera image is a synthetic field with the hole and the end effector projected to pixels; "
            "it is not rendered from a camera link and does not match upstream's 100x100x1 OpenGL image "
            "(rlenv.py:193-238)",
            "the fake seeds its own target draw and repeats a trajectory for a seed; upstream ignores the seed and "
            "draws from the module-level random generator, and its PyBullet client is not seeded "
            "(rlenv.py:97-117)",
            "timestep_ms is 0: the fake applies one action per step without modelling simulated time; upstream calls "
            "p.stepSimulation() ten times per step (rlenv.py:92-95, 154) and the clone does not state PyBullet's "
            "timestep",
            "no actuator, sensor or noise model: the reward follows the distance formula (rlenv.py:240-251) but the "
            "motion that produces the distance is idealized",
            "snapshot and restore are not offered: the environment exposes no get_state or set_state",
            "the upstream environment was not importable where the gate runs (it needs pybullet and the clone's "
            "URDF files) and package code never imports the clone, so the fake was not compared with a real "
            "upstream run",
        ],
    }
