"""OpenMHS driver for gh.jr-robotics/robo-gym: the ExampleEnvSim-v0 Gymnasium environment.

A GymnasiumDriver is configuration only: ``env_id`` names the environment and the bridge derives the whole contract
from the environment's spaces.  ``cap.world.step.v1`` takes ``{ticks, action}`` where the action is a two-element
``Box`` from -1.0 to 1.0, ``cap.world.reset.v1`` takes ``{seed, options}`` (``options.position`` is the initial
``[x, y]``) and ``cap.world.seed.v1`` ``{seed}``.  The device is simulated (R0): there is no hardware backend and no
path to a physical machine in this package.

The clone is the environment layer only.  ``ExampleEnvSim`` starts an external robot server with ``roslaunch
example_robot_server robot_server.launch`` (example_env.py:228) and every ``reset``/``step`` talks to that server
through gRPC (example_env.py:89-99 and :128-133).  The server side lives in the separate robo-gym-robot-servers
repository (README.md:102-103) and is not in this clone, so the gate's ``fake`` backend is this package's in-memory
stand-in for the environment's spaces, step counter and reset options.  A backend name that ``backends`` does not
list (``sim``) is served by ``gymnasium.make(env_id)`` (GymnasiumDriver.open_native): that needs the upstream package
and its dependencies, launches nothing without an ``ip`` argument, and was not run here.

The ``fidelity`` attribute describes the model as deployed by this package (spec 05-fidelity FID-002): the fake is a
kinematic placeholder, not Gazebo, so it claims F0 only.  Every fact cites a line of the clone at the pinned commit
(f086bc90068c41ffd1889d290f3766d69291bf26).  This package is model-authored and unreviewed: it is checked on the fake
backend only.
"""

from mhs.driver import Fact, GymnasiumDriver

ENV = "robo_gym/envs/example/example_env.py"
SIM = "robo_gym/envs/simulation_wrapper.py"


class RoboGymExampleEnv(GymnasiumDriver):
    device_id = "robogym-example"
    env_id = "ExampleEnvSim-v0"
    native = "robo_gym.envs:ExampleEnvSim"
    backends = {"fake": ".fake:FakeExampleEnv"}
    action_space_ref = f"{ENV}:224"
    display_name = "robo-gym ExampleEnvSim-v0 (Gymnasium simulation wrapper)"
    vendor, model = "JR Robotics", "ExampleEnvSim-v0"
    tags = ["robo-gym", "gymnasium", "simulation", "example environment", "reinforcement learning",
            "robot server"]
    facts = [
        Fact("ExampleEnvSim-v0 is registered with entry point robo_gym.envs:ExampleEnvSim",
             source="upstream_code", ref="robo_gym/__init__.py:6-9"),
        Fact("ExampleEnvSim sets cmd to 'roslaunch example_robot_server robot_server.launch' and starts the "
             "simulation through the Simulation wrapper", source="upstream_code", ref=f"{ENV}:227-232"),
        Fact("Simulation starts the simulated robot server with sm_client.start_new_server(cmd=self.cmd, "
             "gui=self.gui)", source="upstream_code", ref=f"{SIM}:56-64"),
        Fact("ExampleEnv declares max_episode_steps = 300", source="upstream_code", ref=f"{ENV}:25"),
        Fact("The action space is a Box of two elements, each from -1.0 to 1.0", source="upstream_code",
             ref=f"{ENV}:224"),
        Fact("The observation space is a Box of four unbounded elements", source="upstream_code",
             ref=f"{ENV}:211-214"),
        Fact("The environment state is [pos_x, pos_y, lin_vel, ang_vel] taken from the robot server state "
             "dictionary", source="upstream_code", ref=f"{ENV}:192-198"),
        Fact("reset takes options.position as the initial [x, y], asserts exactly two elements and defaults to "
             "[0, 0]", source="upstream_code", ref=f"{ENV}:67-73"),
        Fact("reset writes the initial state to the robot server and reads it back; every reset requires the "
             "client created from rs_address", source="upstream_code", ref=f"{ENV}:86-99"),
        Fact("step increments elapsed_steps, rejects an action outside the action space, sends "
             "action.tolist() to the robot server and returns (state, reward, done, False, info)",
             source="upstream_code", ref=f"{ENV}:119-147"),
        Fact("reward returns 0 and done=True with info final_status 'max_steps_exceeded' once elapsed_steps "
             "reaches max_episode_steps", source="upstream_code", ref=f"{ENV}:109-117"),
        Fact("Simulation.close kills the simulated robot server when one is running", source="upstream_code",
             ref=f"{SIM}:89-108"),
    ]
    safe_state = ("the simulation stops advancing: no step or reset is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the environment state is kept and stays readable")
    #: The contract of the model this package deploys (the fake), not of Gazebo: no dynamics, no contacts and no
    #: fixed timestep are present in the clone (the external robot server owns them), so the level is F0.
    fidelity = {
        "engine": "robo-gym:ExampleEnvSim-v0 (external robot server and Gazebo not included)",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "reset(seed) and cap.world.seed.v1 record a seed for the next reset; the fake itself has no "
                     "randomness, so a fixed seed and command sequence always repeats a trajectory, while upstream "
                     "randomness lives in the external robot server and its Gazebo world",
        },
        "timestep_ms": 0.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "no dynamics are in this clone: reset and step forward to an external robot server that is not part "
            "of robo-gym, so the fake is a kinematic placeholder and makes no force, contact or actuator claim",
            "no fixed timestep is declared in this clone: timestep_ms is 0 and one tick is one environment step "
            "whose server-side duration is unknown",
            "no wall-clock pacing: realtime_factor 0, ticks advance only the environment step counter",
            "the observation is whatever the external robot server reports; the fake returns four placeholder "
            "numbers and no rendering",
            "no sensor, noise, contact or actuator model, and no snapshot or restore (the environment exposes no "
            "get_state or set_state)",
            "no physical device is modelled and nothing was validated against one",
        ],
    }
