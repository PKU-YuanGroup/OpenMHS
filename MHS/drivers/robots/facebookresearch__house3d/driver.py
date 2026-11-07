"""OpenMHS driver for gh.facebookresearch/house3d: the RoomNav task of the House3D simulator (Gymnasium family).

A GymnasiumDriver is configuration only: the bridge derives the ``cap.world.*`` contract from the environment's
spaces.  The upstream task is a legacy ``gym.Env`` (``House3D/roomnav.py:76``) that the caller constructs from a
renderer and a house (``House3D/roomnav.py:431-445``); no Gym id is registered for it, so ``env_id`` is left
unset.  The package serves the discrete-action configuration: with ``discrete_action=True`` the action space is
``Discrete(13)`` (``House3D/roomnav.py:131-133`` and the 13 tuples at ``:49-55``), so ``cap.world.step.v1`` takes
``{ticks, action: {index}}`` with ``index`` from 0 to 12.  ``cap.world.reset.v1`` takes ``{seed, options}`` and
``cap.world.seed.v1`` ``{seed}``.

Why the package cannot drive the real simulator here: ``House3D.roomnav`` imports the compiled ``objrender``
pybind extension (``House3D/roomnav.py:18``), and running the task needs SUNCG house data, a ``config.json`` and
OpenCV (``INSTRUCTION.md:59-63``).  The ``fake`` backend is therefore the package's own pure Python RoomNav
stand-in on a small kinematic grid (``fake.py``), not the upstream environment.  The package declares no hardware
backend: the device is simulated (R0), and its e-stop is the runtime's software latch, with no path to a machine.

The ``fidelity`` attribute is the complete contract of the model as deployed (spec 05-fidelity FID-002).  It is
F0 because the stand-in models positions and state transitions directly, without dynamics or contacts.  This
package is model-authored and unreviewed: it is checked on the fake backend only, and no run of the upstream
environment was made.
"""

from mhs.driver import Fact, GymnasiumDriver

ROOMNAV = "House3D/roomnav.py"
CORE = "House3D/core.py"


class House3DRoomNav(GymnasiumDriver):
    device_id = "house3d-roomnav"
    native = "House3D.roomnav:RoomNavTask"
    backends = {"fake": ".fake:FakeRoomNavTask"}
    display_name = "House3D RoomNav (discrete actions)"
    vendor, model = "Facebook Research", "House3D RoomNav"
    tags = ["house3d", "roomnav", "navigation", "3d-scenes", "suncg", "reinforcement-learning", "simulation"]
    facts = [
        Fact("House3D is a virtual 3D environment of thousands of indoor scenes sourced from the SUNCG dataset, "
             "with over 45k indoor 3D scenes", source="vendor_doc", ref="README.md:7-9"),
        Fact("Agents observe RGB images, depth, segmentation masks and top-down 2D map views", source="vendor_doc",
             ref="README.md:11-13"),
        Fact("RoomNavTask is a gym.Env subclass", source="upstream_code", ref=f"{ROOMNAV}:76"),
        Fact("RoomNavTask requires its env argument to be an Environment instance", source="upstream_code",
             ref=f"{ROOMNAV}:110"),
        Fact("The constructor defaults segment_input=True, joint_visual_signal=False, depth_signal=True and "
             "discrete_action=False", source="upstream_code", ref=f"{ROOMNAV}:82-87"),
        Fact("The observation space is Box(0, 255) with shape (resolution[0], resolution[1], n_channel), where "
             "n_channel starts at 3, gains 3 for joint_visual_signal and 1 for depth_signal",
             source="upstream_code", ref=f"{ROOMNAV}:119-127"),
        Fact("The pixel criteria are stated for the default resolution 120 x 90", source="upstream_code",
             ref=f"{ROOMNAV}:58"),
        Fact("The thirteen discrete actions are forward, left, right, left-forward, right-forward, rotate left, "
             "rotate right, backward, small forward, small left, small right, small rotate left and small rotate "
             "right", source="upstream_code", ref=f"{ROOMNAV}:49-54"),
        Fact("n_discrete_actions is len(discrete_actions)", source="upstream_code", ref=f"{ROOMNAV}:55"),
        Fact("discrete_action=True selects spaces.Discrete(n_discrete_actions); otherwise the action space is a "
             "Tuple of Box(0, 1, (4,)) and Box(0, 1, (2,))", source="upstream_code", ref=f"{ROOMNAV}:131-135"),
        Fact("rotation_sensitivity is 30 degrees per time step and default_move_sensitivity is 0.5",
             source="upstream_code", ref=f"{ROOMNAV}:45-46"),
        Fact("success_distance_range is 1.0, success_stay_time_steps is 5 and success_see_target_time_steps is 2",
             source="upstream_code", ref=f"{ROOMNAV}:40-42"),
        Fact("The reward constants are collision_penalty_reward 0.3, stay_room_reward 0.1 and success_reward 10",
             source="upstream_code", ref=f"{ROOMNAV}:30-34"),
        Fact("reset clears the episode counters, resets the house and target, draws a birth place with "
             "random.choice, teleports the environment and returns the rendered observation",
             source="upstream_code", ref=f"{ROOMNAV}:215-245"),
        Fact("step scales the action tuple by move_sensitivity and rot_sensitivity, rotates then moves, charges "
             "the collision penalty when move_forward returns False, adds the in-room reward at distance zero and "
             "adds the success reward when _is_success returns True", source="upstream_code",
             ref=f"{ROOMNAV}:286-319"),
        Fact("max_steps > 0 ends the episode when current_episode_step reaches max_steps", source="upstream_code",
             ref=f"{ROOMNAV}:321-322"),
        Fact("Environment.info returns house_id, loc, yaw, grid, front and right", source="upstream_code",
             ref=f"{CORE}:259-264"),
        Fact("RoomNavTask.info adds dist, scaled_dist, optsteps, collision and target_room", source="upstream_code",
             ref=f"{ROOMNAV}:370-378"),
        Fact("move_forward translates by the forward and horizontal distances and returns whether move accepted "
             "the new position", source="upstream_code", ref=f"{CORE}:196-207"),
        Fact("rotate adds the degrees to the camera yaw", source="upstream_code", ref=f"{CORE}:209-215"),
        Fact("Environment.reset teleports the agent to x, y and yaw and draws a random connected coordinate and a "
             "yaw in [-180, 180) when they are not given", source="upstream_code", ref=f"{CORE}:231-246"),
        Fact("Setting seed in Environment seeds numpy and Python's random module", source="upstream_code",
             ref=f"{CORE}:67-69"),
        Fact("MultiHouseEnv builds one House per id in a multiprocessing Pool and reset_house selects a house by "
             "index or at random", source="upstream_code", ref=f"{CORE}:347-381"),
        Fact("The upstream install requirements are gym and numpy only", source="upstream_code",
             ref="setup.py:17-20"),
    ]
    safe_state = ("the simulation stops advancing: no step or reset is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the world state is kept and stays readable")
    #: The fidelity contract of the stand-in as deployed (spec 05-fidelity section 2).  F0: the model is kinematic,
    #: with positions and transitions modelled directly and no dynamics or contacts.  The bridge derives the engine,
    #: the determinism kind and the lockstep clock; they are written out so the whole contract reads in one place.
    fidelity = {
        "engine": "House3D RoomNavTask (kinematic discrete-action stand-in)",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "reset(seed) reseeds the Python random.Random that draws the birth cell and yaw, and the "
                     "stand-in's motion is deterministic; the upstream task seeds numpy and Python's random module "
                     "in its constructor (House3D/roomnav.py:137-139).  One tick is one navigation step, not a "
                     "fixed physics interval, so timestep_ms is 0.",
        },
        "timestep_ms": 0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "the fake is a kinematic 5x5 grid stand-in, not the SUNCG renderer: no RGB, depth or semantic "
            "rendering, no house geometry, no collision mesh and no SUNCG data",
            "the upstream observation is a Box of shape (resolution[0], resolution[1], n_channel), (120, 90, 4) at "
            "the default resolution named in House3D/roomnav.py:58 with the defaults of :82-84 and :119-127; the "
            "fake returns a 4x4x4 coarse array (marked placeholder in fake.py) to keep receipts small",
            "the reward is reduced to the collision penalty, the in-room reward and the success reward; the "
            "linear, indicator, delta and speed shaping of step() (House3D/roomnav.py:324-345) is not modelled",
            "success is modelled as being within success_distance_range of the target for "
            "success_see_target_time_steps steps; the upstream 'see' criterion counts semantic pixels of target "
            "objects (n_pixel_for_object_see at House3D/roomnav.py:57-60)",
            "the continuous Tuple action space (House3D/roomnav.py:135) is not modelled: the fake uses "
            "discrete_action=True and Discrete(13), the alternative the upstream constructor offers",
            "reset accepts seed and options as the gymnasium bridge requires; the upstream reset takes only a "
            "target and seeds in the constructor (House3D/roomnav.py:77-87, 215)",
            "the upstream environment could not be run here: objrender is a compiled pybind extension "
            "(House3D/roomnav.py:18) and SUNCG data, config.json and OpenCV are required (INSTRUCTION.md:59-63); "
            "the fake was never compared with it",
            "snapshot and restore are not offered: RoomNavTask has set_state but no get_state",
        ],
    }
