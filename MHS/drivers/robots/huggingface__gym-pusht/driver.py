"""OpenMHS driver for gh.huggingface/gym-pusht: the PushT environment (a Gymnasium family driver).

A GymnasiumDriver is configuration only: ``env_id`` names the registered environment and the bridge derives the whole
contract from the environment's spaces.  ``cap.world.step.v1`` takes ``{ticks, action}`` with the action
``{values: [x, y]}`` bounded element by element by the 2-element ``Box(low=0, high=512)`` of ``PushTEnv``,
``cap.world.reset.v1`` takes ``{seed, options}`` and ``cap.world.seed.v1`` ``{seed}``.  The device is simulated (R0):
there is no hardware backend, no e-stop path to a machine and no operator-required limit.

The configuration is the registered environment: ``gym_pusht/__init__.py:3-8`` registers ``gym_pusht/PushT-v0`` with
``entry_point gym_pusht.envs:PushTEnv``, ``max_episode_steps`` 300 and ``kwargs={"obs_type": "state"}``.  That
observation type is the 5-value state vector; the other types ``environment_state_agent_pos``, ``pixels`` and
``pixels_agent_pos`` (``pusht.py:59-65``) would need another ``env_kwargs`` and are not served by this package.

The gate cannot import gym_pusht (pymunk, shapely, pygame, opencv-python and scikit-image, ``pyproject.toml:24-30``),
and package code never imports the clone, so the ``fake`` backend is the package's own pure Python environment.  A
backend name that ``backends`` does not list (``sim``) is served by ``gymnasium.make(env_id)``
(GymnasiumDriver.open_native); that path needs the upstream package and was not run here.

The ``fidelity`` attribute is the complete fidelity contract of the model as deployed (spec 05-fidelity FID-002):
every member of ``device.schema.json`` that applies to a simulator without a physical counterpart.  Every constant and
rule cites a line of the clone at the pinned commit (1dce32970bc3d25e7fad5872c3020159bc5eb31f).  This package is
model-authored and unreviewed: it is checked on the fake backend only.
"""

from mhs.driver import Fact, GymnasiumDriver

PUSHT = "gym_pusht/envs/pusht.py"
REGISTRATION = "gym_pusht/__init__.py"


class PushT(GymnasiumDriver):
    device_id = "pusht"
    env_id = "gym_pusht/PushT-v0"
    env_kwargs = {"obs_type": "state"}          # the kwargs of the registration (gym_pusht/__init__.py:7)
    native = "gym_pusht.envs:PushTEnv"
    backends = {"fake": ".fake:FakePushTEnv"}
    action_space_ref = f"{PUSHT}:161"
    display_name = "gym-pusht PushT 2D manipulation simulation (PushT-v0)"
    vendor, model = "Hugging Face", "gym-pusht 0.1.7"
    tags = ["pusht", "2d-manipulation", "reinforcement-learning", "simulation", "pymunk", "gymnasium"]
    facts = [
        Fact("PushT-v0 is registered with entry point gym_pusht.envs:PushTEnv, max_episode_steps 300 and kwargs "
             "obs_type state", source="upstream_code", ref=f"{REGISTRATION}:3-8"),
        Fact("The action space is a Box of two values in the range 0 to 512", source="upstream_code",
             ref=f"{PUSHT}:161"),
        Fact("The action [x, y] is the target position of the agent", source="upstream_code",
             ref=f"{PUSHT}:50-51"),
        Fact("With obs_type state the observation space is a Box of five values: the agent x and y and the block x "
             "and y bounded by 0 and 512 and the block angle bounded by 0 and 2*pi", source="upstream_code",
             ref=f"{PUSHT}:184-190"),
        Fact("The state observation is [agent_x, agent_y, block_x, block_y, block_angle] and the block angle is "
             "taken modulo 2*pi", source="upstream_code", ref=f"{PUSHT}:382-386"),
        Fact("The PD control gains are k_p 100 and k_v 20", source="upstream_code", ref=f"{PUSHT}:164"),
        Fact("Each physics substep adds acceleration = k_p * (action - agent position) + k_v * (0 - agent velocity) "
             "times dt to the agent velocity", source="upstream_code", ref=f"{PUSHT}:247-250"),
        Fact("The physics timestep is dt 0.01 s and control_hz is the metadata render_fps", source="upstream_code",
             ref=f"{PUSHT}:165-166"),
        Fact("metadata render_fps is 10, which control_hz takes as the control rate", source="upstream_code",
             ref=f"{PUSHT}:135"),
        Fact("One step runs int(1 / (dt * control_hz)) = 10 physics substeps of dt, so it advances 0.1 s of "
             "simulated time", source="upstream_code", ref=f"{PUSHT}:242"),
        Fact("self.success_threshold is 0.95, so a success needs the block at least 95% in the goal zone",
             source="upstream_code", ref=f"{PUSHT}:181"),
        Fact("The reward is coverage / success_threshold clipped to 0 and 1, and the episode terminates when the "
             "coverage is above the success threshold", source="upstream_code", ref=f"{PUSHT}:256-258"),
        Fact("step always returns truncated False: the 300-step limit is the TimeLimit wrapper that "
             "gymnasium.make adds", source="upstream_code", ref=f"{PUSHT}:265"),
        Fact("The coverage is the area of the intersection of the goal tee and the block tee over the area of the "
             "goal tee", source="upstream_code", ref=f"{PUSHT}:232-238"),
        Fact("The goal pose is x 256, y 256 and angle pi/4 radians", source="upstream_code", ref=f"{PUSHT}:447"),
        Fact("The agent is a kinematic circle of radius 15 that starts at (256, 400)", source="upstream_code",
             ref=f"{PUSHT}:445"),
        Fact("The block starts at (256, 300) with angle 0, and add_tee builds the tee from two rectangles with "
             "scale 30, length 4 and mass 1", source="upstream_code", ref=f"{PUSHT}:446"),
        Fact("add_tee sets the body centre of gravity to the mean of the two rectangle centres of gravity",
             source="upstream_code", ref=f"{PUSHT}:511"),
        Fact("The goal body of get_goal_pose_body never sets a centre of gravity", source="upstream_code",
             ref=f"{PUSHT}:403-412"),
        Fact("The walls are four segments at x 5, x 506, y 5 and y 506 with radius 2", source="upstream_code",
             ref=f"{PUSHT}:436-441"),
        Fact("The physics space has gravity 0 and damping 0.0 when no damping argument is given",
             source="upstream_code", ref=f"{PUSHT}:430-432"),
        Fact("A reset draws the agent x and y from the integers 50 to 449, the block x and y from 100 to 399 and "
             "the block angle uniformly from -pi to pi", source="upstream_code", ref=f"{PUSHT}:276-284"),
        Fact("Passing the reset option reset_to_state sets the state from the option", source="upstream_code",
             ref=f"{PUSHT}:272-273"),
        Fact("_set_state puts the first two state values on the agent, the next two on the block position and the "
             "last on the block angle", source="upstream_code", ref=f"{PUSHT}:456-462"),
        Fact("info carries pos_agent, vel_agent, block_pose, goal_pose and n_contacts", source="upstream_code",
             ref=f"{PUSHT}:414-424"),
        Fact("step adds coverage and is_success to info", source="upstream_code", ref=f"{PUSHT}:261-263"),
    ]
    safe_state = ("the simulation stops advancing: no step, reset or seed is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the environment state is kept and stays readable")
    #: The fidelity contract of the model as deployed (spec 05-fidelity section 2).  The bridge derives the engine,
    #: the determinism kind and the lockstep clock; they are written out so the whole contract reads in one place.
    fidelity = {
        "engine": "gymnasium:gym_pusht/PushT-v0",
        "fidelity_level": "F1",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "reset(seed) or cap.world.seed.v1 fixes the environment's random generator, which draws the "
                     "agent and block start poses (gym_pusht/envs/pusht.py:276-284), and the pymunk rigid-body "
                     "solver is deterministic, so one implementation repeats a trajectory for the same seed and "
                     "actions; this package's fake draws the start poses with Python's random.Random while "
                     "upstream draws them from numpy's generator, so one seed gives different start poses on the "
                     "two",
        },
        "timestep_ms": 100.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "pymunk rigid-body dynamics with contacts: the collision solver, the collision friction and the exact "
            "moment of inertia of the tee are approximated in the fake backend by a two-rectangle contact "
            "resolution, an inelastic wall stop and a worked-out area overlap, so trajectories differ from the "
            "upstream environment and were never compared with it",
            "the fake backend clamps the agent and the block at the wall segments (gym_pusht/envs/pusht.py:436-441); "
            "upstream resolves the wall collisions in pymunk and its kinematic agent is not stopped by a wall",
            "the reward and the terminal state follow the coverage definition "
            "(gym_pusht/envs/pusht.py:232-238, :256-258) exactly for the geometry, but which block poses the fake "
            "reaches is decided by its simplified contacts",
            "no wall-clock pacing: realtime_factor 0, one tick runs 10 physics substeps of dt 0.01 s and advances "
            "0.1 s of simulated time (gym_pusht/envs/pusht.py:242)",
            "no rendering and no image observation: only the obs_type state observation is served; render(), the "
            "human window and the pixels, pixels_agent_pos and environment_state_agent_pos observation types are "
            "not modelled",
            "snapshot and restore are not offered: PushTEnv exposes no get_state or set_state",
        ],
    }
