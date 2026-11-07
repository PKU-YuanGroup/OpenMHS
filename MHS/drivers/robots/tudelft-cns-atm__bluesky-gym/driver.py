"""OpenMHS driver for gh.tudelft-cns-atm/bluesky-gym: the ``DescentEnv-v0`` environment (a Gymnasium family driver).

BlueSky-Gym registers seven air-traffic environments (``bluesky_gym/__init__.py:4-46``).  This package serves
``DescentEnv-v0``: the vertical-control task in which the agent commands the aircraft's vertical speed while the
aircraft approaches a runway (``bluesky_gym/envs/descent_env.py:31``).  A ``GymnasiumDriver`` is configuration only:
``env_id`` names the environment and the bridge derives the whole contract from the environment's spaces.
``cap.world.step.v1`` takes ``{ticks, action}`` with the action ``{values: [v]}`` bounded by ``Box(-1, 1, (1,))``
(``descent_env.py:61``), ``cap.world.reset.v1`` takes ``{seed, options}`` and ``cap.world.seed.v1`` ``{seed}``.
The device is simulated (R0): there is no hardware backend, no e-stop path to a machine and no operator-required
limit.

The gate cannot import the upstream package (it needs ``bluesky-simulator``, gymnasium, numpy, pygame, torch and
stable-baselines3, ``pyproject.toml:4-11``, and package code never imports the clone), so the ``fake`` backend is the
package's own pure-Python stand-in (fake.py).  A backend name that ``backends`` does not list (``sim``) is served by
``gymnasium.make("DescentEnv-v0")`` after the upstream registration (``GymnasiumDriver.open_native`` and
``bluesky_gym/__init__.py:4-10``); that path was not run here.

The ``fidelity`` attribute is the contract of the model as deployed (spec 05-fidelity FID-002).  The clone shows an
aircraft advanced by BlueSky at a fixed ``DT`` and a vertical-speed command (``descent_env.py:71`` and ``:145-159``);
it shows no force, contact, actuator or sensor model, so this package claims F0 and names what is absent in ``gaps``.
Every constant and rule cites a line of the clone at the pinned commit
(``8d7d79c63a3dab5de0e7bd8c2afb74737377f2e5``).  This package is model-authored and unreviewed: it is checked on the
fake backend only, and its evidence is ``contract_checked``, never an MHS-Device level.
"""

from mhs.driver import Fact, GymnasiumDriver

ENV = "bluesky_gym/envs/descent_env.py"
INIT = "bluesky_gym/__init__.py"


class Descent(GymnasiumDriver):
    device_id = "bluesky-descent"
    env_id = "DescentEnv-v0"
    native = "bluesky_gym.envs.descent_env:DescentEnv"
    backends = {"fake": ".fake:FakeDescentEnv"}
    display_name = "BlueSky-Gym DescentEnv-v0 (vertical control)"
    vendor, model = "TU Delft CNS/ATM", "DescentEnv-v0"
    tags = ["air-traffic-management", "bluesky", "descent", "vertical-control", "reinforcement-learning",
            "simulation", "gymnasium"]
    facts = [
        Fact("DescentEnv-v0 is registered with entry point bluesky_gym.envs.descent_env:DescentEnv and "
             "max_episode_steps=300", source="upstream_code", ref=f"{INIT}:6-10"),
        Fact("DescentEnv is a gymnasium.Env subclass", source="upstream_code", ref=f"{ENV}:31"),
        Fact("The action space is a Box from -1 to 1 with shape (1,)", source="upstream_code", ref=f"{ENV}:61"),
        Fact("The observation space is a Dict of altitude, vz, target_altitude and runway_distance, each a Box "
             "from -inf to +inf", source="upstream_code", ref=f"{ENV}:52-59"),
        Fact("ACTION_2_MS is 12.5", source="upstream_code", ref=f"{ENV}:17"),
        Fact("_get_action multiplies the action by ACTION_2_MS and its comment says the result is metres per "
             "second", source="upstream_code", ref=f"{ENV}:145-147"),
        Fact("A non-negative action sets the target altitude to 1000000 (a climb command) and a negative action "
             "sets it to 0 (a descent command) before setting the selected vertical speed",
             source="upstream_code", ref=f"{ENV}:154-159"),
        Fact("The environment sends BlueSky the stack command 'DT 1;FF'", source="upstream_code", ref=f"{ENV}:71"),
        Fact("ACTION_FREQUENCY is 30", source="upstream_code", ref=f"{ENV}:29"),
        Fact("step calls bs.sim.step() ACTION_FREQUENCY times before it reads the observation",
             source="upstream_code", ref=f"{ENV}:187-194"),
        Fact("A reset draws the initial altitude with np.random.randint(ALT_MIN, ALT_MAX) and the target altitude "
             "as that altitude plus np.random.randint(-TARGET_ALT_DIF, TARGET_ALT_DIF)",
             source="upstream_code", ref=f"{ENV}:169-170"),
        Fact("ALT_MIN is 2000, ALT_MAX is 4000 and TARGET_ALT_DIF is 500", source="upstream_code",
             ref=f"{ENV}:23-25"),
        Fact("A reset creates KL001 as an A320 at the drawn altitude with speed AC_SPD and switches VNAV off",
             source="upstream_code", ref=f"{ENV}:172-173"),
        Fact("AC_SPD is 150", source="upstream_code", ref=f"{ENV}:27"),
        Fact("The observation normalisation constants are ALT_MEAN 1500, ALT_STD 3000, VZ_MEAN 0, VZ_STD 5, "
             "RWY_DIS_MEAN 100 and RWY_DIS_STD 200", source="upstream_code", ref=f"{ENV}:10-15"),
        Fact("The observation divides (altitude - ALT_MEAN) by ALT_STD, (vz - VZ_MEAN) by VZ_STD, "
             "(target_altitude - ALT_MEAN) by ALT_STD and (runway_distance - RWY_DIS_MEAN) by RWY_DIS_STD",
             source="upstream_code", ref=f"{ENV}:104-107"),
        Fact("runway_distance is DEFAULT_RWY_DIS (200) minus the great-circle distance from 52N 4E to the "
             "aircraft times NM2KM (1.852)", source="upstream_code", ref=f"{ENV}:94-101"),
        Fact("The reward is abs(target_altitude - altitude) * ALT_DIF_REWARD_SCALE while the runway is ahead and "
             "the altitude is positive, CRASH_PENALTY when the altitude is zero or below, and altitude * "
             "RWY_ALT_DIF_REWARD_SCALE when the runway is reached", source="upstream_code", ref=f"{ENV}:127-143"),
        Fact("ALT_DIF_REWARD_SCALE is -5/3000, CRASH_PENALTY is -100 and RWY_ALT_DIF_REWARD_SCALE is -50/3000",
             source="upstream_code", ref=f"{ENV}:19-21"),
        Fact("A terminated step deletes every aircraft from the BlueSky traffic", source="upstream_code",
             ref=f"{ENV}:200-203"),
        Fact("close sends 'quit' to the BlueSky stack", source="upstream_code", ref=f"{ENV}:276-277"),
    ]
    safe_state = ("the simulation stops advancing: after an e-stop the runtime refuses step and reset until "
                  "mhs.safety.reset clears the latch, and the last world state stays readable")
    #: The fidelity contract of the model as deployed (spec 05-fidelity section 2).  The clone shows no force,
    #: contact, actuator, sensor or noise model, so the level is F0 and the gaps say so.
    fidelity = {
        "engine": "bluesky:DescentEnv-v0",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "reset(seed) or cap.world.seed.v1 fixes the initial altitude and the target altitude; this "
                     "package's fake then integrates its deterministic analytic descent.  Upstream draws those "
                     "two values with numpy's generator and integrates BlueSky's aircraft performance model, so "
                     "one seed gives different trajectories on the two implementations",
        },
        "timestep_ms": 30000.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "kinematic/analytic model: no forces, contacts, aircraft performance, actuator, sensor or noise model; "
            "the fake moves the altitude by the commanded vertical speed and closes the runway distance at a "
            "placeholder rate",
            "one cap.world.step.v1 tick applies one action and then runs ACTION_FREQUENCY=30 BlueSky simulation "
            "steps at the environment's DT 1 setting (descent_env.py:29 and :71); timestep_ms is the 30-step "
            "per-tick period, and the clone states no unit for DT",
            "the fake draws the reset altitude and target with Python's random.Random; upstream uses numpy's "
            "generator, so one seed gives different initial states",
            "the fake's initial runway distance and closure rate are placeholders, not the BlueSky aircraft "
            "position and ground speed; upstream computes runway_distance from the great-circle distance to "
            "52N 4E (descent_env.py:94-101)",
            "the fake does not render the rgb_array or human frames the environment declares "
            "(descent_env.py:45)",
            "snapshot and restore are not offered: the environment exposes no get_state or set_state",
            "no physical device is modelled and the model was never validated against one",
            "no wall-clock pacing: realtime_factor 0, and a tick advances simulated time by 30000 ms only",
        ],
    }
