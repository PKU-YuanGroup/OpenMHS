"""OpenMHS driver for gh.svengronauer/phoenix-drone-simulation: the DroneHoverSimpleEnv-v0 environment.

A GymnasiumDriver is configuration only: ``env_id`` names the registered environment and the bridge derives the
whole contract from its spaces.  ``cap.world.step.v1`` takes ``{ticks, action}`` with ``action.values`` as the four
normalized motor commands in [-1, 1], ``cap.world.reset.v1`` takes ``{seed, options}`` and ``cap.world.seed.v1``
``{seed}``.  The device is simulated (R0): there is no hardware backend, no e-stop path to a machine and no
operator-required limit.

The gate cannot import the upstream package (setup.py:24-34 needs gymnasium, pybullet, numpy, torch and more), so the
``fake`` backend is this package's pure Python implementation of the simplified hover dynamics (fake.py).  A backend
name that ``backends`` does not list (``sim``) would be served by ``gymnasium.make(env_id)``
(GymnasiumDriver.open_native); that path needs the upstream package and was not run here.

Every Fact cites a line of the clone at the pinned commit c5d690732976351f5bbea4161913d98c376a4f04.  This package is
model-authored and unreviewed: it is checked on the fake backend only.
"""

from mhs.driver import Fact, GymnasiumDriver

HOVER = "phoenix_drone_simulation/envs/hover.py"
BASE = "phoenix_drone_simulation/envs/base.py"
AGENTS = "phoenix_drone_simulation/envs/agents.py"


class DroneHover(GymnasiumDriver):
    device_id = "phoenix-hover"
    env_id = "DroneHoverSimpleEnv-v0"
    native = "phoenix_drone_simulation.envs.hover:DroneHoverSimpleEnv"
    backends = {"fake": ".fake:FakeDroneHoverEnv"}
    action_space_ref = 'phoenix_drone_simulation/envs/base.py:148-150'
    display_name = "Phoenix Drone Simulation DroneHoverSimpleEnv-v0"
    vendor, model = "Sven Gronauer", "CrazyFlie 2.1 / DroneHoverSimpleEnv-v0"
    tags = ["drone", "quadrotor", "crazyflie", "reinforcement-learning", "simulation", "gymnasium"]
    facts = [
        Fact("DroneHoverSimpleEnv-v0 is the hover task with PWM control at 100 Hz, simple physics, 100 Hz "
             "observations, 10% domain randomization, no aerodynamic effects and instant motor force",
             source="vendor_doc", ref="README.md:30"),
        Fact("DroneHoverSimpleEnv-v0 is registered with max_episode_steps=500", source="upstream_code",
             ref="phoenix_drone_simulation/__init__.py:9-11"),
        Fact("The CrazyFlie agent has four control channels (act_dim=4)", source="upstream_code",
             ref=f"{AGENTS}:134"),
        Fact("The action space bounds each of the four control channels to [-1, 1]", source="upstream_code",
             ref=f"{BASE}:148-150"),
        Fact("The observation history keeps two (observation, action) pairs", source="upstream_code",
             ref=f"{BASE}:44"),
        Fact("The observation space is a Box bounded by +-1000 whose width is the history length times the "
             "observation plus action width", source="upstream_code", ref=f"{BASE}:143-149"),
        Fact("With observation noise enabled, the observation concatenates position, quaternion, linear velocity "
             "and angular rate", source="upstream_code", ref=f"{HOVER}:159"),
        Fact("The hover target is the position [0, 0, 1.0]", source="upstream_code", ref=f"{HOVER}:14"),
        Fact("The hover episode terminates when roll or pitch passes 60 degrees, altitude falls below 0.2 m or an "
             "angular rate passes 300 degrees per second", source="upstream_code", ref=f"{HOVER}:93-100"),
        Fact("The terminal penalty defaults to 100", source="upstream_code", ref=f"{HOVER}:21"),
        Fact("The reward is minus the Euclidean distance to the target minus the action, angle, spin, velocity and "
             "terminal penalties", source="upstream_code", ref=f"{HOVER}:169-186"),
        Fact("A reset draws a position offset of +-0.25 m, roll and pitch of +-pi/6 rad, yaw of +-2pi rad, linear "
             "velocity of +-0.1 m/s and angular rate of +-200 deg/s (yaw +-20 deg/s)", source="upstream_code",
             ref=f"{HOVER}:200-228"),
        Fact("reset accepts a seed keyword but the body does not read it", source="upstream_code",
             ref=f"{BASE}:382-429"),
        Fact("The initial state is drawn with numpy's global random generator through np.random.uniform and "
             "np.random.normal", source="upstream_code", ref=f"{HOVER}:200-228"),
        Fact("Observation noise is enabled by default (observation_noise=1)", source="upstream_code",
             ref=f"{HOVER}:12"),
        Fact("Domain randomization defaults to 0.10", source="upstream_code", ref=f"{HOVER}:13"),
        Fact("The simple hover environment uses SimplePhysics with the cf21x_sys_eq drone model and sim_freq=100 Hz",
             source="upstream_code", ref=f"{HOVER}:258-263"),
        Fact("The physics timestep is 1/SIM_FREQ", source="upstream_code", ref=f"{BASE}:98"),
    ]
    safe_state = ("the simulation stops advancing: no step or reset is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the environment state is kept and stays readable")
    #: The fidelity contract of the model as deployed (spec 05-fidelity section 2).  The bridge derives the engine,
    #: the determinism kind and the lockstep clock; they are written out so the whole contract reads in one place.
    fidelity = {
        "engine": "gymnasium:DroneHoverSimpleEnv-v0",
        "fidelity_level": "F1",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "this package's fake draws the reset state from random.Random(seed) and its dynamics are "
                     "deterministic, so one seed and action sequence repeat a trajectory; upstream reset() accepts "
                     "but ignores seed (base.py:382-429) and draws from numpy's global generator, so a seed gives "
                     "different trajectories on the two",
        },
        "timestep_ms": 10.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "the fake integrates the simplified rigid-body equations of SimplePhysics with an ideal PWM-to-thrust "
            "map: no contacts, drag, ground effect or motor dynamics, and the 10% domain randomization of the "
            "upstream environment is not applied",
            "observation noise (observation_noise=1 upstream, hover.py:12) is not modelled; the fake returns the "
            "13-value noiseless observation that the upstream 100 Hz branch would produce",
            "upstream reset() accepts but ignores seed and draws the initial state from numpy's global generator "
            "(base.py:382-429, hover.py:203-228); the fake uses random.Random(seed), so a seed does not repeat an "
            "upstream trajectory",
            "the fake was not compared with the upstream PyBullet environment and no physical device is modelled; "
            "nothing was validated",
            "no wall-clock pacing: realtime_factor 0, ticks advance simulated time by timestep_ms (10 ms) only",
            "snapshot and restore are not offered: the environment exposes no get_state or set_state",
        ],
    }
