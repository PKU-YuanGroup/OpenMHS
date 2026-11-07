"""OpenMHS driver for gh.etaoxing/kitchen-shift: the ``Kitchen_v0`` MuJoCo kitchen environment.

A GymnasiumDriver is configuration only: ``env_id`` names the registered environment and the bridge derives the
step contract from the environment's action and observation spaces.  ``cap.world.step.v1`` takes
``{ticks, action}`` with ``action`` the ``Box(-1, 1, shape=(9,))`` of the default ``absvel`` control mode
(``kitchen_v0.py:107-108`` and ``:129``); ``cap.world.reset.v1`` takes ``{seed, options}`` and
``cap.world.seed.v1`` takes ``{seed}``.  The device is simulated (R0): there is no hardware backend, no e-stop
path to a machine and no operator-required limit.

The driver names the card's first entry symbol, ``kitchen_shift.kitchen_v0:Kitchen_v0``, and the clone's registered
id ``kitchen-v0`` (``kitchen_shift/__init__.py:6-10``).  The card's second entry symbol, ``Kitchen_v1``, is a
separate environment and is not covered by this package.

The gate cannot import the upstream environment (it needs MuJoCo, dm_control and gym, ``kitchen_v0.py:15-24``), so
the ``fake`` backend is the package's own pure Python stand-in (fake.py).  A backend name that ``backends`` does not
list (``sim``) is served by ``gym.make(env_id)`` (GymnasiumDriver.open_native); that path needs the upstream package
and MuJoCo and was not run here.  This package is model-authored and unreviewed: it is checked on the fake backend
only.

Every Fact cites a line of the read-only clone at commit 6d0928000d4843df43791d3efd9e58af72c3acac.  The fidelity
contract below describes the fake as deployed, not the upstream MuJoCo model (spec 05-fidelity FID-002).
"""

from mhs.driver import Fact, GymnasiumDriver

KITCHEN = "kitchen_shift/kitchen_v0.py"
REGISTRATION = "kitchen_shift/__init__.py"
MODEL = "kitchen_shift/assets/kitchen.xml"


class KitchenShiftV0(GymnasiumDriver):
    device_id = "kitchen-v0"
    env_id = "kitchen-v0"
    native = "kitchen_shift.kitchen_v0:Kitchen_v0"
    backends = {"fake": ".fake:FakeKitchenV0"}
    action_space_ref = f"{KITCHEN}:129"
    display_name = "KitchenShift kitchen-v0 (MuJoCo Franka kitchen)"
    vendor, model = "Eliot Xing et al.", "Kitchen_v0"
    tags = ["kitchen", "manipulation", "mujoco", "franka", "reinforcement-learning", "simulation", "gym"]
    facts = [
        Fact("Kitchen_v0 is a gym.Env subclass described as a kitchen manipulation environment in MuJoCo",
             source="upstream_code", ref=f"{KITCHEN}:37-38"),
        Fact("The environment imports dm_control, mujoco, gym and numpy", source="upstream_code",
             ref=f"{KITCHEN}:15-24"),
        Fact("The robot has 9 degrees of freedom and the object state has 21", source="upstream_code",
             ref=f"{KITCHEN}:63-64"),
        Fact("The default control mode is 'absvel'", source="upstream_code", ref=f"{KITCHEN}:42"),
        Fact("In the absvel control mode the action dimension is 9", source="upstream_code",
             ref=f"{KITCHEN}:107-108"),
        Fact("The action space is gym.spaces.Box(-1.0, 1.0, shape=(action_dim,))", source="upstream_code",
             ref=f"{KITCHEN}:129"),
        Fact("act_mid is zeros(action_dim) and act_amp is 2.0 * ones(action_dim)", source="upstream_code",
             ref=f"{KITCHEN}:130-131"),
        Fact("The action is clipped to [-1, 1] and then mapped to act_mid + a * act_amp", source="upstream_code",
             ref=f"{KITCHEN}:222-225"),
        Fact("The observation dict has the keys robot_qp, robot_qv, obj_qp and obj_qv", source="upstream_code",
             ref=f"{KITCHEN}:178-183"),
        Fact("The observation arrays are cast to float32", source="upstream_code", ref=f"{KITCHEN}:189-191"),
        Fact("The observation space is a Dict of Box spaces bounded by -inf and inf, shaped by the observation "
             "dict", source="upstream_code", ref=f"{KITCHEN}:133-137"),
        Fact("step returns the observation dict, reward 0.0, done False and an empty info dict", source="upstream_code",
             ref=f"{KITCHEN}:215-220"),
        Fact("reset restores the simulator and returns the observation; objects_done_set selects elements whose "
             "goal pose is restored", source="upstream_code", ref=f"{KITCHEN}:293-305"),
        Fact("seed(seed) creates the environment's numpy random generator and returns [seed]", source="upstream_code",
             ref=f"{KITCHEN}:361-363"),
        Fact("The MuJoCo model timestep is 0.002 s", source="upstream_code", ref=f"{MODEL}:16"),
        Fact("The default frame_skip is 40", source="upstream_code", ref=f"{KITCHEN}:44"),
        Fact("kitchen-v0 is registered as a gym environment with max_episode_steps=280", source="upstream_code",
             ref=f"{REGISTRATION}:6-10"),
    ]
    safe_state = ("the simulation stops advancing: no step or reset is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the environment state is kept and stays readable")
    #: The fidelity contract of the fake as deployed.  The bridge derives the engine, determinism and clock, and
    #: the gaps say what the fake does not model.
    fidelity = {
        "engine": "mujoco:kitchen-v0",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "reset(seed) or cap.world.seed.v1 selects the Python random generator that draws the fake's "
                     "placeholder initial jitter, so one seed and one action sequence repeat on the fake; upstream "
                     "seeds numpy's generator (kitchen_v0.py:361-363), which feeds the observation noise rather "
                     "than the reset pose, and this fake was not compared with it",
        },
        "timestep_ms": 80.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "the fake backend is not MuJoCo: it has no contacts, actuator dynamics, robot controller or observation "
            "noise, and its transition is a placeholder first-order motion of 9 robot positions plus a 9-vector of "
            "robot velocities; the 21 object positions and velocities stay at their placeholder values",
            "the observation arrays have the upstream dimensions (robot_qp 9, robot_qv 9, obj_qp 21, obj_qv 21, "
            "kitchen_v0.py:63-64) but placeholder values; they were not compared with an upstream rollout",
            "the 280-step TimeLimit of the registration (__init__.py:9) is modelled as truncation, although the "
            "bare Kitchen_v0.step never ends an episode (kitchen_v0.py:215-220)",
            "no rendering, no worldgen wrapper and no object goal poses of reset(objects_done_set) are modelled",
            "seed changes only the fake's placeholder initial jitter; the upstream seed feeds the observation-noise "
            "generator and its reset pose is deterministic",
            "snapshot and restore are not offered: the environment exposes no get_state or set_state",
            "no physical device is modelled and nothing was validated against hardware or against the upstream "
            "simulator",
        ],
    }
