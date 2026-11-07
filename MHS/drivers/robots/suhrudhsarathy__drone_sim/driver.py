"""OpenMHS driver for gh.suhrudhsarathy/drone_sim: the SimpleDroneEnv legacy Gym quadcopter simulator.

A GymnasiumDriver is configuration only: the family bridge derives ``cap.world.step.v1`` (``{ticks, action}`` with
the action ``{values: [w1, w2, w3, w4]}`` bounded by the environment's ``Box(0, 1, (4,))``), ``cap.world.reset.v1``
(``{seed, options}``) and ``cap.world.seed.v1`` (``{seed}``) from the environment's spaces.  The environment is a
legacy Gym environment (``gym.Env``; its ``step`` returns the four-value tuple and its ``reset`` takes no seed), which
the bridge serves through the same ``cap.world.*`` classes.  The device is simulated (R0): there is no hardware
backend, no e-stop path to a machine and no operator-required limit.

The upstream environment is not registered with ``gym.make`` and the gate must not import the clone, so the ``fake``
backend is the package's own pure-Python re-implementation (fake.py).  The ``native`` class is the card's entry
symbol; gate G7 checks the fake against it and never imports it.

The ``fidelity`` attribute is the complete fidelity contract of the model as deployed (spec 05-fidelity FID-002).
Every constant and rule cites a line of the clone at the pinned commit
(1a324f178a5719676bdb0caaa2a2d545a7158fdd).  This package is model-authored and unreviewed: it is checked on the
fake backend only.
"""

from mhs.driver import Fact, GymnasiumDriver

ENV = "drone_sim/gym/simple_drone_env.py"
DRONE = "drone_sim/sim/drone.py"
PARAMS = "drone_sim/sim/parameters.py"


class SimpleDrone(GymnasiumDriver):
    device_id = "drone-sim"
    native = "drone_sim.gym.simple_drone_env:SimpleDroneEnv"
    backends = {"fake": ".fake:FakeSimpleDroneEnv"}
    display_name = "drone_sim SimpleDroneEnv (legacy Gym quadcopter)"
    vendor, model = "Suhrudh Sarathy", "SimpleDroneEnv"
    tags = ["drone", "quadcopter", "rigid-body", "reinforcement-learning", "simulation", "gym"]
    facts = [
        Fact("The environment class SimpleDroneEnv subclasses gym.Env", source="upstream_code", ref=f"{ENV}:11"),
        Fact("The action space is a Box of four float32 values in [0, 1]", source="upstream_code", ref=f"{ENV}:35"),
        Fact("The observation space is a Box of shape (3, 3) whose low and high are both -inf", source="upstream_code",
             ref=f"{ENV}:30-36"),
        Fact("The environment constructs Drone(0, 0, 2, enable_death=False) and sets init_position to [0, 0, 2]",
             source="upstream_code", ref=f"{ENV}:19-28"),
        Fact("The environment stores the module constant NULL_ROT and step multiplies the action by it before "
             "Drone.step", source="upstream_code", ref=f"{ENV}:40-46"),
        Fact("NULL_ROT = 620.2943", source="upstream_code", ref=f"{PARAMS}:15"),
        Fact("Drone.step maps four values to w1 = v0, w2 = -v1, w3 = v2, w4 = -v3 and then calls update",
             source="upstream_code", ref=f"{DRONE}:117-122"),
        Fact("The observation has three rows: [x, y, z], [ax, ay, az] and [p, q, r]", source="upstream_code",
             ref=f"{ENV}:50-56"),
        Fact("The reward is 1 - dist(current, init_position) / dist(goal_position, init_position)",
             source="upstream_code", ref=f"{ENV}:58-62"),
        Fact("A roll or pitch beyond 60 degrees or a z below 0 sets done, resets the drone and subtracts 5 from the "
             "reward; a distance below 0.01 from init_position sets done and adds 10", source="upstream_code",
             ref=f"{ENV}:64-78"),
        Fact("Step returns (observation, reward, done, info), the legacy four-value API", source="upstream_code",
             ref=f"{ENV}:84"),
        Fact("Reset takes no seed and no options; it calls Drone.__reset__ and returns the observation",
             source="upstream_code", ref=f"{ENV}:86-97"),
        Fact("Drone.__reset__ restores the position (0, 0, 0.5) and zeroes the angles, velocities and p, q, r",
             source="upstream_code", ref=f"{DRONE}:101-115"),
        Fact("The simulation advances by a fixed step DT = 0.004 between updates", source="upstream_code",
             ref=f"{PARAMS}:4"),
        Fact("The drone parameters are mass 0.468, K = 2.980e-6, B = 1.140e-7, L = 0.225 and G = 9.8",
             source="upstream_code", ref=f"{PARAMS}:8-13"),
        Fact("The inertia is IXX = IYY = 4.856e-3 and IZZ = 8.801e-3", source="upstream_code",
             ref=f"{PARAMS}:18-20"),
        Fact("The drag coefficients are AX = AY = AZ = 0.25", source="upstream_code", ref=f"{PARAMS}:23-25"),
        Fact("Thrust is K times the sum of the four squared rotor speeds along body z", source="upstream_code",
             ref=f"{DRONE}:163-169"),
        Fact("The torque is [L*K*(w1^2-w3^2), L*K*(w2^2-w4^2), B*(w1^2-w2^2+w3^2-w4^2)]", source="upstream_code",
             ref=f"{DRONE}:171-177"),
        Fact("Acceleration is gravity plus (1/mass) times the rotated thrust plus (1/mass) times the drag force",
             source="upstream_code", ref=f"{DRONE}:183-185"),
        Fact("p, q and r are overwritten with the angular acceleration from the inertia and the torque",
             source="upstream_code", ref=f"{DRONE}:187-197"),
        Fact("update integrates with Euler steps: angle += angular velocity*DT, velocity += acceleration*DT and "
             "position += the updated velocity*DT", source="upstream_code", ref=f"{DRONE}:209-228"),
        Fact("normalise_theta keeps an angle in the -pi to pi range", source="upstream_code", ref=f"{DRONE}:231-241"),
    ]
    safe_state = ("the simulation stops advancing: no step or reset is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the world state is kept and stays readable")
    fidelity_level = "F1"
    #: The fidelity contract of the model as deployed (spec 05-fidelity section 2).
    fidelity = {
        "engine": "custom:drone_sim.sim.drone",
        "fidelity_level": "F1",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "the rigid-body update is deterministic and the upstream reset() restores a fixed state "
                     "without using the seed; the bridge records the seed, so one seed and a command sequence "
                     "repeat, but different seeds do not change the trajectory",
        },
        "timestep_ms": 4.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "rigid-body dynamics with an ideal rotor-to-thrust and rotor-to-torque mapping: no contact model, no "
            "ground or obstacle collision; a z below 0 or a tilt beyond 60 degrees simply resets the drone",
            "the rotor speed is an ideal input (action * NULL_ROT); there is no motor, battery, aerodynamic or "
            "sensor-noise model in the environment",
            "no wall-clock pacing: realtime_factor 0, ticks advance simulated time by 4 ms only",
            "the fake backend re-implements the dynamics in pure Python with nested lists rather than numpy "
            "float32 arrays, and it was not compared with a run of the upstream environment",
            "seed control is nominal: the upstream reset() takes no seed and restores the same fixed state, so the "
            "seed is recorded but does not change the trajectory",
            "snapshot and restore are not offered: the environment exposes no get_state or set_state",
            "the fake does not render; upstream render() calls a matplotlib Graphics window",
        ],
    }
