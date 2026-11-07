"""OpenMHS driver for gh.farama-foundation/minigrid: the BlockedUnlockPickup environment (a Gymnasium family driver).

A GymnasiumDriver is configuration only: ``env_id`` names the environment and the bridge derives the whole contract
from the environment's spaces.  ``cap.world.step.v1`` takes ``{ticks, action}`` with the action ``{index}`` bounded by
``Discrete(7)`` (the seven MiniGrid actions of ``minigrid/core/actions.py``), ``cap.world.reset.v1`` takes
``{seed, options}`` and ``cap.world.seed.v1`` ``{seed}``.  The environment is simulated (R0): there is no hardware
backend, no e-stop path to a machine and no operator-required limit.

The card is a driver pack: the repository holds one environment class per file and the card lists five entry symbols.
This package covers the first of them, ``minigrid.envs:BlockedUnlockPickupEnv``, registered as
MiniGrid-BlockedUnlockPickup-v0 (minigrid/__init__.py:17-20); facts.md names the other four classes as not covered.

The gate cannot import the clone (the upstream needs numpy, gymnasium and pygame-ce, pyproject.toml), so the ``fake``
backend is the package's own pure Python MiniGrid world (fake.py).  A backend name that ``backends`` does not list
(``sim``) is served by ``gymnasium.make(env_id)`` (GymnasiumDriver.open_native); that path needs the upstream package
and was not run here (README.md).

The ``fidelity`` attribute is the fidelity contract of the model as deployed (spec 05-fidelity FID-002).  Every
constant and rule cites a line of the clone at the pinned commit (b34a5755dbef71e3f1662552259a94b255c1a8bb).  This
package is model-authored and unreviewed: it is checked on the fake backend only.
"""

from mhs.driver import Fact, GymnasiumDriver

ENVFILE = "minigrid/envs/blockedunlockpickup.py"
BASE = "minigrid/minigrid_env.py"
ROOMGRID = "minigrid/core/roomgrid.py"
CONSTANTS = "minigrid/core/constants.py"
ACTIONS = "minigrid/core/actions.py"


class BlockedUnlockPickup(GymnasiumDriver):
    device_id = "minigrid-blocked-unlock-pickup"
    env_id = "MiniGrid-BlockedUnlockPickup-v0"
    native = "minigrid.envs:BlockedUnlockPickupEnv"
    backends = {"fake": ".fake:FakeBlockedUnlockPickupEnv"}
    display_name = "MiniGrid BlockedUnlockPickup (MiniGrid-BlockedUnlockPickup-v0)"
    vendor, model = "Farama Foundation", "MiniGrid-BlockedUnlockPickup-v0"
    tags = ["minigrid", "gridworld", "reinforcement-learning", "simulation", "gymnasium"]
    facts = [
        Fact("BlockedUnlockPickupEnv is registered as MiniGrid-BlockedUnlockPickup-v0 with the entry point "
             "minigrid.envs:BlockedUnlockPickupEnv", source="upstream_code", ref="minigrid/__init__.py:17-20"),
        Fact("The seven actions are left 0, right 1, forward 2, pickup 3, drop 4, toggle 5 and done 6",
             source="upstream_code", ref=f"{ACTIONS}:6-20"),
        Fact("The action space is Discrete(len(actions)), i.e. Discrete(7)", source="upstream_code",
             ref=f"{BASE}:63"),
        Fact("The observation space is a Dict of image = Box(low=0, high=255, shape=(agent_view_size, "
             "agent_view_size, 3), dtype=uint8), direction = Discrete(4) and the mission space", source="upstream_code",
             ref=f"{BASE}:72-83"),
        Fact("agent_view_size defaults to 7", source="upstream_code", ref=f"{BASE}:42"),
        Fact("The direction is 0 right, 1 down, 2 left, 3 up (DIR_TO_VEC), and the direction string map is "
             "'>', 'V', '<', '^'", source="upstream_code", ref=f"{CONSTANTS}:48-57"),
        Fact("Each tile is encoded as (OBJECT_IDX, COLOR_IDX, STATE) and the door STATE is 0 open, 1 closed, "
             "2 locked", source="upstream_code", ref=f"{ENVFILE}:41-47"),
        Fact("OBJECT_TO_IDX maps unseen 0, empty 1, wall 2, floor 3, door 4, key 5, ball 6, box 7, goal 8, lava 9, "
             "agent 10; COLOR_TO_IDX maps red 0, green 1, blue 2, purple 3, yellow 4, grey 5", source="upstream_code",
             ref=f"{CONSTANTS}:20-37"),
        Fact("step increments step_count and then branches on the action: left decrements the direction, right "
             "increments it, forward moves when the front cell is empty or can be overlapped, pickup and drop move "
             "an object, toggle activates the front cell, and the done action does nothing",
             source="upstream_code", ref=f"{BASE}:525-582"),
        Fact("The episode is truncated when step_count reaches max_steps", source="upstream_code",
             ref=f"{BASE}:587-588"),
        Fact("The success reward is 1 - 0.9 * (step_count / max_steps)", source="upstream_code", ref=f"{BASE}:245"),
        Fact("BlockedUnlockPickupEnv ends the episode when the agent picks up the target box, with the success "
             "reward", source="upstream_code", ref=f"{ENVFILE}:107-115"),
        Fact("The room grid is (room_size - 1) * num_rows + 1 high and (room_size - 1) * num_cols + 1 wide",
             source="upstream_code", ref=f"{ROOMGRID}:89-90"),
        Fact("BlockedUnlockPickupEnv uses two rooms of size 6 (num_rows 1, num_cols 2, so a 6 x 11 grid) and "
             "max_steps = 16 * room_size**2 when it is not given", source="upstream_code",
             ref=f"{ENVFILE}:72-83"),
        Fact("The generated grid puts a box in the right room, a locked door between the rooms, a ball that blocks "
             "the door, a key in the left room and the agent in the left room", source="upstream_code",
             ref=f"{ENVFILE}:89-105"),
    ]
    safe_state = ("the simulation stops advancing: no step or reset is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the world state is kept and stays readable")
    fidelity = {
        "engine": "gymnasium:MiniGrid-BlockedUnlockPickup-v0",
        "fidelity_level": "F1",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "reset(seed) or cap.world.seed.v1 fixes the mission colour and the initial world, and the "
                     "dynamics are deterministic, so one implementation repeats a trajectory for the same seed and "
                     "actions; this package's fake draws its colours with Python's random.Random while upstream uses "
                     "numpy's generator, so a seed gives different worlds on the two",
        },
        "timestep_ms": 0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "the world is a 6 x 11 two-room grid with a locked door, a ball, a key and a target box; it is a "
            "simplified stand-in for the upstream generator and was never compared with a run of the upstream "
            "environment (the upstream needs numpy, gymnasium and pygame-ce, which the gate does not have)",
            "simulated time does not advance: MiniGrid is turn-based, so timestep_ms is 0 and a tick is one action",
            "the image is encoded with the constants of the clone (7 x 7 x 3, OBJECT_TO_IDX/COLOR_TO_IDX/"
            "STATE_TO_IDX), but the agent's view is fully visible: no view-slicing occlusion (process_vis) and no "
            "partial observability behind walls is modelled",
            "the mission text is drawn from the six colour names of COLOR_NAMES; upstream samples it from a "
            "MissionSpace, so the text is the same kind of string but not the same distribution",
            "the clone exposes no get_state/set_state (it has a state hash only, minigrid/minigrid_env.py:159), so "
            "snapshot and restore are not offered and determinism is 'seeded', not 'exact'",
            "rendering is not modelled and no physical device is modelled; nothing was validated against a device",
        ],
    }
