"""OpenMHS driver for gh.gustavo-moura/itomori: the Navigation2DEnv UAV environment (a Gymnasium family driver).

A GymnasiumDriver is configuration only: ``env_id`` names the environment and the bridge derives the whole contract
from the environment's spaces.  ``cap.world.step.v1`` takes ``{ticks, action}`` with ``action.values`` the Box order
``[angle change, velocity change]``, ``cap.world.reset.v1`` takes ``{seed, options}`` and ``cap.world.seed.v1``
``{seed}``.  The device is simulated (R0): there is no hardware backend, no e-stop path to a machine and no
operator-required limit.

The gate cannot import gymnasium (it is not installed where the gate runs) and package code never imports the clone,
so the ``fake`` backend is the package's own pure Python model of the default no-obstacle map.  A backend name that
``backends`` does not list (``sim``) is served by ``gymnasium.make(env_id)`` (GymnasiumDriver.open_native); that path
needs gymnasium, numpy, scipy, pygame and matplotlib and was not run here (the upstream default map path does not
match the data in the clone either; see the fidelity gaps).

The ``fidelity`` attribute is the complete fidelity contract of the model as deployed (spec 05-fidelity FID-002).
Every fact cites a line of the clone at the pinned commit (0c2da173bf989736f919772d3c6cbc2fea098b72).  This package is
model-authored and unreviewed: it is checked on the fake backend only.
"""

from mhs.driver import Fact, GymnasiumDriver

NAV = "itomori/envs/navigation2d.py"
CONFIG = "itomori/envs/configs.py"
MAP = "itomori/envs/navigation2d_configs/maps/10x10/10x10_NoObstacle.json"


class ItomoriNavigation2D(GymnasiumDriver):
    device_id = "itomori_navigation2d"
    env_id = "itomori/Navigation2DEnv-v0"
    native = "itomori.envs:Navigation2DEnv"
    backends = {"fake": ".fake:FakeNavigation2DEnv"}
    display_name = "Itomori Navigation2D UAV environment"
    vendor, model = "Gustavo de Moura", "Navigation2DEnv-v0"
    tags = ["uav", "navigation", "risk-aware", "reinforcement-learning", "simulation", "gymnasium"]
    facts = [
        Fact("itomori/Navigation2DEnv-v0 is registered with entry point itomori.envs:Navigation2DEnv and "
             "max_episode_steps=300", source="upstream_code", ref="itomori/__init__.py:3-7"),
        Fact("The constructor defaults render_mode to 'human' and accepts only 'human' or 'rgb_array'",
             source="upstream_code", ref=f"{NAV}:21-39"),
        Fact("The constructor's default map_filepath is the relative path "
             "itomori/navigation2d_config/maps/10x10/10x10_NoObstacle.json", source="upstream_code",
             ref=f"{NAV}:22"),
        Fact("default_uav_args sets velocity_initial 0, velocity_min 0, velocity_max 50, velocity_change_min -10, "
             "velocity_change_max 100, angle_initial 0, angle_change_min -10, angle_change_max 10, delta_T 0.1, "
             "gps_uncertainty_initial 0.5 and gps_uncertainty_increment 0.02", source="upstream_code",
             ref=f"{CONFIG}:2-13"),
        Fact("load_uav_args documents velocity in m/s, angle change in degrees/s, velocity change in m/s**2, "
             "delta_T in s and GPS uncertainty in m", source="upstream_code", ref=f"{NAV}:133-140"),
        Fact("The observation space is a Dict of origin (x, y in 0..50), destination (x, y in 0..size) and "
             "agent_location (x, y in 0..size; velocity in velocity_min..velocity_max; angle unbounded and "
             "risk/GPS uncertainty in 0..inf)", source="upstream_code", ref=f"{NAV}:79-98"),
        Fact("The action space is a Box(2) of [angle change, velocity change] with low "
             "[angle_change_min, velocity_change_min] and high [angle_change_max, velocity_change_max], dtype float",
             source="upstream_code", ref=f"{NAV}:100-111"),
        Fact("The starting agent location is [origin x, origin y, velocity_initial, angle_initial]",
             source="upstream_code", ref=f"{NAV}:55-62"),
        Fact("_move unpacks the action as ac, vc = action, so the first action value is the angle change and the "
             "second the velocity change", source="upstream_code", ref=f"{NAV}:325"),
        Fact("A step sets velocity to v + velocity_change*delta_T clipped to [velocity_min, velocity_max] and the "
             "angle to a + angle_change*delta_T clipped to [angle_change_min, angle_change_max]", source="upstream_code",
             ref=f"{NAV}:329-335"),
        Fact("A step then advances x by v_next*cos(angle_next)*delta_T + velocity_change*cos(angle_next)*delta_T**2/2 "
             "(sin for y) and clips each coordinate to [0, size]", source="upstream_code", ref=f"{NAV}:337-343"),
        Fact("reset sets timestep 0, previous_agent_location None, the agent at the starting location with risk from "
             "chance_constraint and the current gps_uncertainty, and the history to that one location",
             source="upstream_code", ref=f"{NAV}:217-235"),
        Fact("step increments timestep, adds gps_uncertainty_increment to gps_uncertainty, appends the new location "
             "to the history, and returns observation, reward, terminated, truncated=False and info",
             source="upstream_code", ref=f"{NAV}:237-261"),
        Fact("destination_tolerance is 1.5 m", source="upstream_code", ref=f"{NAV}:46"),
        Fact("is_done is true when the distance to the destination is below destination_tolerance or the agent "
             "failed", source="upstream_code", ref=f"{NAV}:202-212"),
        Fact("is_outofbounds is true when any coordinate is <= 0 or >= size", source="upstream_code",
             ref=f"{NAV}:214-215"),
        Fact("is_failed is true when the agent is out of bounds or its segment hits an obstacle", source="upstream_code",
             ref=f"{NAV}:194-200"),
        Fact("The reward is distance_weight*distance + steps_weight*len(agent_location_history) + risk_weight*risk, "
             "and math.inf when the agent failed", source="upstream_code", ref=f"{NAV}:349-369"),
        Fact("reward_weights defaults to distance 0.9, steps 0.1 and risk 0, and the constructor asserts that the "
             "weights sum to 1", source="upstream_code", ref=f"{NAV}:24-42"),
        Fact("A map JSON declares size in m, origin [x, y], destination [x, y] and a list of polygon obstacles",
             source="upstream_code", ref=f"{NAV}:162-166"),
        Fact("The 10x10_NoObstacle.json map has size 10, origin [1, 1], destination [9, 9] and no obstacles",
             source="upstream_code", ref=f"{MAP}:1-6"),
        Fact("step always returns truncated=False", source="upstream_code", ref=f"{NAV}:255"),
    ]
    safe_state = ("the simulation stops advancing: no step or reset is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the environment state is kept and stays readable")
    #: The fidelity contract of the model as deployed (spec 05-fidelity section 2).  The bridge derives the engine,
    #: the determinism kind and the lockstep clock; they are written out so the whole contract reads in one place.
    fidelity = {
        "engine": "itomori:Navigation2DEnv-v0",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "reset(seed) and cap.world.seed.v1 are accepted, but the environment draws no random numbers: "
                     "a reset always starts at the map origin, so the same seed and actions reproduce the same "
                     "trajectory.  The bridge reports seeded because the environment exposes no get_state/set_state "
                     "for exact replay; the fake uses the same equations as the upstream class.",
        },
        "timestep_ms": 100.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "F0 kinematic point model: an action applies a velocity change and an angle change directly; there is "
            "no mass, force, drag, actuator, contact or friction model",
            "no sensor or noise model: GPS uncertainty is a deterministic increment per step and risk is the "
            "obstacle chance constraint; the fake models the no-obstacle map, so its risk is always 0",
            "no wall-clock pacing: realtime_factor 0, ticks advance simulated time by timestep_ms (delta_T 0.1 s) "
            "only",
            "no physical device is modelled and the model was never validated against one",
            "the fake backend re-implements only the default 10x10 no-obstacle map, ignores map files, obstacles and "
            "the uav/reward configuration, and was not compared with the upstream environment",
            "the upstream default map_filepath (itomori/navigation2d_config/maps/10x10/10x10_NoObstacle.json) does "
            "not match the data in the clone (itomori/envs/navigation2d_configs/maps/10x10/10x10_NoObstacle.json), "
            "so the sim backend needs an explicit map_filepath and was not run",
            "the fake returns Python lists where upstream returns numpy arrays; both compute in float64 but the "
            "trigonometric calls and operation order differ, so state hashes can differ in the last bits",
            "snapshot and restore are not offered: the environment exposes no get_state or set_state",
        ],
    }
