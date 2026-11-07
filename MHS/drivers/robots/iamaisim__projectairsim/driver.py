"""OpenMHS Gymnasium driver for the Project AirSim drone-landing environment.

The card selected a ROS helper from the repository's static scan, but the
card's AST-confirmed entry symbols are OpenAI Gym environments, not a ROS
transport.  The repository does contain ROS 2 nodes, but the environment
itself is a Python ``gym.Env`` that talks to a Project AirSim simulator
through the projectairsim client, so this package is a ``GymnasiumDriver``
over the concrete ``ProjectAirSimDroneLandingEnv`` implementation.

The native ``step`` is a coroutine and ``reset`` takes no arguments.  Both
backends declare the SDK's ``asyncio_owned_loop_v1`` profile: one owned event
loop awaits ``step`` and calls ``reset``, ``close``, the remote stop
(``world.pause``) and its probe (``world.is_paused``) within declared local
bounds; a call that outlives its bound stays owned and is never cancelled
locally.  The fake keeps the native calling convention with analytic
kinematics.  The live ``sim`` backend constructs the pinned environment lazily
(sim.py); it has not been run against a Project AirSim server.

DEVIATION FROM THE CARD: helper ``RosDriver`` was replaced by
``GymnasiumDriver`` because the card's confirmed entry symbol is a Gymnasium
environment, not a ROS endpoint.  See RESULT.json notes.
"""

from mhs.driver import Fact, GymnasiumDriver

#: The pinned environment is a gym.Env wrapper around the client and world.
_ENV_FILE = "client/python/projectairsim/src/projectairsim/gym_envs/projectairsim_dronelanding_env.py"
_BASE_FILE = "client/python/projectairsim/src/projectairsim/gym_envs/gym_env.py"
_WORLD_FILE = "client/python/projectairsim/src/projectairsim/world.py"
_CLIENT_FILE = "client/python/projectairsim/src/projectairsim/client.py"
_SCENE_FILE = "client/python/projectairsim/src/projectairsim/gym_envs/sim_config/scene_bonsai_drone_landing.jsonc"
_SERVER_SCENE = "core_sim/src/scene.cpp"


#: One owned event loop for every native call. The bounds are local package choices, not upstream facts.
_ASYNC = {
    "mode": "asyncio_owned_loop_v1",
    "step": "coroutine",
    "reset": "sync",
    "reset_kwargs": [],
    "step_timeout_s": 30.0,
    "reset_timeout_s": 120.0,
    "close_timeout_s": 15.0,
    "remote_stop": "world.pause",
    "stop_probe": "world.is_paused",
    "stop_timeout_s": 5.0,
    "settle_timeout_s": 10.0,
    "source_refs": [f"{_ENV_FILE}:32", f"{_ENV_FILE}:63-88", f"{_WORLD_FILE}:114-126",
                    f"{_WORLD_FILE}:238-250", f"{_SERVER_SCENE}:706-752", f"{_SCENE_FILE}:14-19"],
}


class ProjectAirSimDroneLanding(GymnasiumDriver):
    """The pinned drone-landing environment behind an owned event loop; analytic fake for the gate."""

    device_id = "projectairsim-drone-landing"
    device_kind = "world.sim"
    mode = "simulated"
    risk = "R0"
    native = ("projectairsim.gym_envs.projectairsim_dronelanding_env:"
              "ProjectAirSimDroneLandingEnv")
    env_id = "ProjectAirSimDroneLanding-v0"
    backends = {"fake": ".fake:FakeProjectAirSimDroneLanding", "sim": ".sim:make_env"}
    async_by_backend = {"fake": _ASYNC, "sim": _ASYNC}
    #: The action space bound the fake copies (NED velocity commands, m/s): a literal path:LINE for show_refs.py.
    action_space_ref = "client/python/projectairsim/src/projectairsim/gym_envs/projectairsim_dronelanding_env.py:30"
    tags = ["gymnasium", "gym", "simulation", "drone", "landing", "projectairsim"]
    display_name = "Project AirSim drone-landing environment"
    vendor = "IAMAI Consulting Corp"
    safe_state = (
        "The scene's steppable simulation clock reports paused (World.pause, read back by World.is_paused; Unreal "
        "is not asked to confirm) and no native step, reset or close is owned; a running continue_for_sim_time is "
        "not interrupted. Further step and reset are refused until mhs.safety.reset clears the latch."
    )
    fidelity = {
        "determinism": {
            "kind": "none",
            "seed_control": "none",
            "notes": ("The native reset takes no seed; the fake is deterministic analytic code, but no simulator or "
                      "flight-controller determinism is claimed for either backend."),
        },
        "reset": "full",
        "snapshot_restore": False,
    }
    fidelity_by_backend = {
        "fake": {
            "engine": "analytic:Python drone-landing stand-in (no Project AirSim server or Unreal)",
            "fidelity_level": "F0",
            "gaps": [
                "the fake is an analytic kinematic stand-in: no dynamics, flight controller, sensors or collision "
                "detection; positions follow the commanded velocity directly",
                "it keeps the native calling convention (coroutine step awaiting a command task, synchronous "
                "argument-free reset, world.pause/is_paused) but runs no Project AirSim client or Unreal scene",
                "the upstream environment never sets done on a successful landing (its own TODO at line 85); the "
                "fake likewise keeps done false",
                "camera, image and perception observations are not part of the selected base environment; only "
                "the 4-element pose/dyaw observation is exposed",
            ],
        },
        "sim": {
            "engine": "projectairsim: Unreal scene SceneBonsaiDroneLanding over a steppable clock",
            "fidelity_level": "F1",
            "gaps": [
                "not run: no Project AirSim server, Unreal scene or flight controller was available; the live "
                "route is a source-reviewed contract, not validated execution",
                "contact and actuator fidelity are those of the Project AirSim scene and flight controller; neither "
                "is validated against a physical drone",
                "the owned loop bounds are local package choices; the client's service socket waits up to 300 s "
                "per request (client.py:59-60)",
                "the pose and collision callbacks run on the client's receive thread; the observation is the latest "
                "pose seen when the step returns",
                "the bridge must be the only client advancing the scene's steppable clock",
            ],
        },
    }
    facts = [
        Fact(
            "ProjectAirSimEnv subclasses gym.Env and, in its constructor, connects a ProjectAirSimClient and "
            "constructs a World from the scene configuration.",
            source="upstream_code",
            ref=f"{_BASE_FILE}:15-29",
        ),
        Fact(
            "ProjectAirSimEnv defines close() as client.disconnect(), while reset() and step() are "
            "NotImplementedError hooks for concrete environments.",
            source="upstream_code",
            ref=f"{_BASE_FILE}:33-51",
        ),
        Fact(
            "The gym registry maps ProjectAirSimDroneLanding-v0 to "
            "ProjectAirSimDroneLandingEnv in projectairsim_dronelanding_env.",
            source="upstream_code",
            ref="client/python/projectairsim/src/projectairsim/gym_envs/__init__.py:14-18",
        ),
        Fact(
            "The drone-landing environment uses a 0.100 s delta/step time, chosen to be longer than the "
            "flight controller's 50 Hz (20 ms) minimum command duration.",
            source="upstream_code",
            ref=f"{_ENV_FILE}:21-23",
        ),
        Fact(
            "The observation shape is (4,) for dx, dy, dz and dyaw, and the action shape is (3,) for "
            "V_north, V_east and V_down.",
            source="upstream_code",
            ref=f"{_ENV_FILE}:25-27",
        ),
        Fact(
            "The observation space is Box(-math.inf, math.inf, shape=(4,)) and the action space is "
            "Box(-1.0, 1.0, shape=(3,)).",
            source="upstream_code",
            ref=f"{_ENV_FILE}:29-30",
        ),
        Fact(
            "reset() loads the scene, creates a Drone, subscribes to its actual_pose and collision_info, "
            "enables API control and arms the vehicle.",
            source="upstream_code",
            ref=f"{_ENV_FILE}:32-59",
        ),
        Fact(
            "step() is async: it calls the drone's move_by_velocity_async with the three action components, "
            "advances the simulated world by dt, awaits the move task and returns the legacy four-tuple "
            "(observation, reward, done, info).",
            source="upstream_code",
            ref=f"{_ENV_FILE}:63-88",
        ),
        Fact(
            "move_by_velocity_async documents v_north, v_east and v_down as desired velocities in world "
            "NED axes in m/s.",
            source="upstream_code",
            ref="client/python/projectairsim/src/projectairsim/drone.py:306-308",
        ),
        Fact(
            "get_observation returns the actor pose relative to the landing pad as dx, dy, dz and the "
            "actor yaw; get_reward returns the L2 distance between the goal and actor poses.",
            source="upstream_code",
            ref=f"{_ENV_FILE}:100-141",
        ),
        Fact(
            "collision_callback stores the collision info and sets done, which is the only path in this "
            "environment that ends an episode.",
            source="upstream_code",
            ref=f"{_ENV_FILE}:191-194",
        ),
        Fact(
            "The environment's own comment marks landing-success termination as an unfinished TODO, so the "
            "pinned episode ends on collision only.",
            source="upstream_code",
            ref=f"{_ENV_FILE}:85",
        ),
        Fact(
            "The drone-landing scene uses a steppable clock with a 5,000,000 ns step that pauses on start.",
            source="upstream_code",
            ref=f"{_SCENE_FILE}:14-19",
        ),
        Fact(
            "World.continue_for_sim_time continues the simulation for delta_time_nanos and then pauses.",
            source="upstream_code",
            ref=f"{_WORLD_FILE}:252-255",
        ),
        Fact(
            "World.pause sends the scene's Pause service request with do_pause True.",
            source="upstream_code",
            ref=f"{_WORLD_FILE}:114-126",
        ),
        Fact(
            "World.is_paused sends the scene's IsPaused service request and returns its boolean answer.",
            source="upstream_code",
            ref=f"{_WORLD_FILE}:238-250",
        ),
        Fact(
            "The server's SimPause supports only a steppable clock, and ContinueForSimTime with "
            "wait_until_complete waits until the clock reports paused.",
            source="upstream_code",
            ref=f"{_SERVER_SCENE}:706-752",
        ),
        Fact(
            "The client's service socket waits up to 300000 ms for a reply to each request.",
            source="upstream_code",
            ref=f"{_CLIENT_FILE}:59-60",
        ),
        Fact(
            "request_async sends on a new socket context and returns an asyncio task that processes the reply.",
            source="upstream_code",
            ref=f"{_CLIENT_FILE}:284-309",
        ),
        Fact(
            "disconnect stops the receive loop, joins the receive thread, unsubscribes and closes both sockets.",
            source="upstream_code",
            ref=f"{_CLIENT_FILE}:419-433",
        ),
        Fact(
            "Inside the async step, the environment advances the world with the synchronous "
            "world.continue_for_sim_time call and only then awaits the move task.",
            source="upstream_code",
            ref=f"{_ENV_FILE}:77-81",
        ),
        Fact(
            "World.continue_for_sim_time sends its ContinueForSimTime request through client.request.",
            source="upstream_code",
            ref=f"{_WORLD_FILE}:263-273",
        ),
        Fact(
            "client.request sends on the service socket and blocks in recv_msg until the reply arrives or the "
            "receive timeout expires.",
            source="upstream_code",
            ref=f"{_CLIENT_FILE}:255-282",
        ),
        Fact(
            "The server's SimPause carries a TODO asking whether it should wait for external components such as "
            "Unreal to confirm the pause before returning.",
            source="upstream_code",
            ref=f"{_SERVER_SCENE}:711-712",
        ),
        Fact(
            "The server's IsPaused service returns the simulation clock's paused flag.",
            source="upstream_code",
            ref=f"{_SERVER_SCENE}:725",
        ),
        Fact(
            "The Linux client setup installs the Python client library from client/python/projectairsim with "
            "pip install -e.",
            source="upstream_code",
            ref="docs/client_setup.md:125-128",
        ),
        Fact(
            "The client's autonomy extra pins gym==0.18.3; the base dependencies do not include gym.",
            source="upstream_code",
            ref="client/python/projectairsim/pyproject.toml:55",
        ),
    ]
