"""OpenMHS driver for gh.riiswa/planning-multi-robot-gym: the PlanningMultiRobot-v0 Gymnasium environment.

A GymnasiumDriver is configuration only: ``env_id`` names the environment and the bridge derives the whole contract
from the environment's spaces.  The action space is a Dict of the two Box arrays ``vR`` and ``vL`` (one wheel-speed
value per robot, each bounded by the environment's ``max_velocity``), so ``cap.world.step.v1`` takes
``{ticks, action: {vR: [...], vL: [...]}}``.  ``cap.world.reset.v1`` takes ``{seed, options}`` and
``cap.world.seed.v1`` takes ``{seed}``.  The device is simulated (R0): there is no hardware backend, no hardware stop
and no operator-required limit.

The gate environment does not have gymnasium or pygame installed, and package code never imports the clone, so the
``fake`` backend is the package's own pure Python simulation (fake.py).  A backend name that ``backends`` does not
list (``sim``) is served by ``gymnasium.make(env_id)`` (GymnasiumDriver.open_native); that path needs the upstream
environment and was not run here; the fidelity gaps and RESULT.json notes say so.

The ``fidelity`` attribute is the complete fidelity contract of the model as deployed (spec 05-fidelity FID-002).
Every Fact cites a line of the clone at the pinned commit dbb4eb5ab82e4143d1d567095eacae7bdb390b0b.  This package is
model-authored and unreviewed: it is checked on the fake backend only.
"""

from mhs.driver import Fact, GymnasiumDriver

ENV = "planning_multi_robot_gym/planning_multi_robot_env.py"
REGISTRATION = "planning_multi_robot_gym/__init__.py"


class PlanningMultiRobotGym(GymnasiumDriver):
    device_id = "planning-multi-robot"
    env_id = "PlanningMultiRobot-v0"
    native = "planning_multi_robot_gym:PlanningMultiRobotEnv"
    backends = {"fake": ".fake:FakePlanningMultiRobotEnv"}
    display_name = "Planning Multi-Robot Gym"
    vendor, model = "riiswa", "PlanningMultiRobot-v0"
    tags = ["multi-robot", "planning", "obstacle-avoidance", "reinforcement-learning", "simulation", "gymnasium"]
    facts = [
        Fact("The environment simulates the movements of multiple robots in an environment with barriers and a "
             "target, and the goal is to navigate the robots to the target while avoiding collisions",
             source="vendor_doc", ref="README.md:5"),
        Fact("The action space is a Dict of two Box arrays named vR and vL, each with one value per robot and each "
             "element bounded by -max_velocity and +max_velocity", source="upstream_code", ref=f"{ENV}:85-90"),
        Fact("The observation is a Dict with vR, vL and theta (one value per robot), robot_positions "
             "(n_robots x 2), future_target_position (2) and future_obstacle_positions ((n_barriers - 1) x 2)",
             source="upstream_code", ref=f"{ENV}:92-113"),
        Fact("The play field corners are x from -4.0 to 4.0 and y from -3.0 to 3.0",
             source="upstream_code", ref=f"{ENV}:80"),
        Fact("A reset draws each barrier position uniformly between the play-field bounds and each barrier "
             "velocity from a normal distribution with standard deviation barrier_velocity_range",
             source="upstream_code", ref=f"{ENV}:154-162"),
        Fact("A reset draws the target index uniformly from 0 to n_barriers - 1",
             source="upstream_code", ref=f"{ENV}:164"),
        Fact("A reset places robot i at x = left play-field corner - 0.5, y = -2.0 + 0.8 * i, with theta 0.0",
             source="upstream_code", ref=f"{ENV}:166"),
        Fact("Barriers move by their velocity times dt on every step, and a velocity component is reversed when "
             "the barrier passes the matching play-field edge", source="upstream_code", ref=f"{ENV}:170-181"),
        Fact("The wheel spacing of the differential-drive model is twice robot_radius",
             source="upstream_code", ref=f"{ENV}:68"),
        Fact("The pose model moves straight when the wheel speeds are equal, rotates in place when they are "
             "opposite, and follows an arc otherwise", source="upstream_code", ref=f"{ENV}:183-212"),
        Fact("A step limits each wheel's speed change to max_acceleration * dt, then integrates the pose over dt",
             source="upstream_code", ref=f"{ENV}:222-238"),
        Fact("The future obstacle and target positions are predicted by advancing a copy of the barriers "
             "steps_ahead_to_plan steps without moving the simulation state",
             source="upstream_code", ref=f"{ENV}:129-144"),
        Fact("A robot closer than barrier_radius + robot_radius to the target barrier earns reach_target_reward "
             "and a new target is drawn; the same distance to another barrier or another robot earns "
             "collision_penalty", source="upstream_code", ref=f"{ENV}:250-264"),
        Fact("An episode is terminated only when reset_when_target_reached is true and a robot reached the target; "
             "truncated is always false", source="upstream_code", ref=f"{ENV}:269"),
        Fact("The info dictionary reports n_robots, max_acceleration, max_velocity, barrier_radius, robot_radius, "
             "dt and tau", source="upstream_code", ref=f"{ENV}:115-124"),
        Fact("The environment is registered as PlanningMultiRobot-v0 with entry point "
             "planning_multi_robot_gym:PlanningMultiRobotEnv", source="upstream_code", ref=f"{REGISTRATION}:5-8"),
        Fact("The environment metadata declares the render modes rgb_array and human with render_fps 30",
             source="upstream_code", ref=f"{ENV}:24"),
    ]
    safe_state = ("the simulation stops advancing: no step or reset is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the environment state is kept and stays readable")
    #: The fidelity contract of the model as deployed (spec 05-fidelity section 2).  The bridge derives the engine,
    #: the determinism kind and the timestep from the environment; they are written out so the whole contract reads in
    #: one place.  timestep_ms is the upstream default dt of 0.1 s (planning_multi_robot_env.py:37).
    fidelity = {
        "engine": "gymnasium:PlanningMultiRobot-v0",
        "fidelity_level": "F1",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "reset(seed) or cap.world.seed.v1 fixes the initial state and the dynamics are deterministic, "
                     "so one implementation repeats a trajectory for the same seed and actions; this package's fake "
                     "draws the initial state with Python's random.Random and upstream with numpy's generator, so a "
                     "seed gives different trajectories on the two",
        },
        "timestep_ms": 100.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "planar differential-drive kinematics of circular robots: no body geometry beyond a radius, no wheel "
            "slip, friction, actuator dynamics, sensor model or noise; collisions are distance tests between "
            "circles, and the target and the barriers move as point-like circles",
            "no wall-clock pacing: realtime_factor 0, ticks advance simulated time by timestep_ms only",
            "no physical device is modelled and the model was never validated against one",
            "the fake backend re-implements the environment with Python floats and random.Random and was not "
            "compared with the upstream environment (the upstream package is not installed and gymnasium/pygame "
            "are absent where the gate runs): trajectories differ from upstream's numpy random stream and array "
            "dtypes",
            "the info member predict_position is a Python callable and is omitted from the JSON state",
            "no rendering: the fake reports render_mode None and returns no frame; cap.world.render.v1 stays "
            "unbound",
            "snapshot and restore are not offered: the environment exposes no get_state or set_state",
        ],
    }
