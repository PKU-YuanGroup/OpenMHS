"""OpenMHS driver for gh.vitchyr/multiworld: the GoalGridworld-v0 environment (a Gymnasium family driver).

``multiworld`` registers ``GoalGridworld-v0`` as a legacy Gym ``GoalEnv`` (gym.envs.registration, not
gymnasium), so the environment's ``reset()`` has no seed argument and ``step()`` returns the four-tuple
``(observation, reward, done, info)``.  ``mhs.bridge.gymnasium.GymnasiumBridge`` accepts exactly those legacy
shapes (it falls back to the four-tuple and to a seedless reset), so the card's ``GymnasiumDriver`` helper is the
right shape: this class is configuration only and the bridge derives the contract from the environment's spaces.

The selected entry symbol is the card's first one, ``multiworld.envs.gridworlds.goal_gridworld:GoalGridworld``.
The card's MuJoCo Sawyer entry symbols (push, door, pick-and-place, reach) are not covered by this package: they
need mujoco-py and the MuJoCo 2.1 binaries, and every one of them is an actuated robot arm rather than a simulated
grid world.  The card's risk floor is R0 and the device is simulated (no hardware backend).

The fake backend is a pure Python re-implementation of the upstream class (the gate never installs or imports the
clone), with the same public members: ``reset``, ``step``, ``move_agent``, ``from_s``, ``to_s``, ``get_obs``,
``imagine_obs`` and ``compute_reward``.  It keeps the real observation size (a 10 x 10 x 1 grid flattened to 100
floats).  The ``fidelity`` block below is the contract of the model as deployed and its ``gaps`` list what is not
modelled.  The package is model-authored and unreviewed; it was checked on the fake backend only.
"""

from mhs.driver import Fact, GymnasiumDriver

GRIDWORLD = "multiworld/envs/gridworlds/goal_gridworld.py"
GRIDWORLD_REGISTRATION = "multiworld/envs/gridworlds/__init__.py"


class GoalGridworldDriver(GymnasiumDriver):
    device_id = "goal_gridworld"
    env_id = "GoalGridworld-v0"
    native = "multiworld.envs.gridworlds.goal_gridworld:GoalGridworld"
    backends = {"fake": ".fake:FakeGoalGridworld"}
    display_name = "Multiworld GoalGridworld-v0 (10 x 10 goal grid)"
    vendor, model = "Vitchyr Pong", "GoalGridworld-v0"
    tags = ["multiworld", "goal-gridworld", "gridworld", "goal-conditioned", "reinforcement-learning",
            "simulation", "gym"]
    facts = [
        Fact("The ACTIONS list defines five actions, in order (-1, 0), (0, 1), (1, 0), (0, -1) and (0, 0)",
             source="upstream_code", ref=f"{GRIDWORLD}:13"),
        Fact("The action space is Discrete(nA), where nA is the length of the ACTIONS list",
             source="upstream_code", ref=f"{GRIDWORLD}:39-45"),
        Fact("GoalGridworld-v0 is registered with entry point "
             "multiworld.envs.gridworlds.goal_gridworld:GoalGridworld and no keyword arguments",
             source="upstream_code", ref=f"{GRIDWORLD_REGISTRATION}:2-5"),
        Fact("The constructor's default grid is 10 rows by 10 columns", source="upstream_code",
             ref=f"{GRIDWORLD}:35-36"),
        Fact("The observation space is a Dict with the members observation, achieved_goal and desired_goal; each "
             "member is a Box of shape (rows, columns, 1) with low 0 and high 1",
             source="upstream_code", ref=f"{GRIDWORLD}:46-49"),
        Fact("A reset draws the agent cell and the goal cell from one random permutation of all grid cells, so "
             "the two cells are distinct, and starts the step count at 0", source="upstream_code",
             ref=f"{GRIDWORLD}:69-76"),
        Fact("move_agent adds the action's offset to the agent row and column and keeps the old cell when the "
             "move would leave the grid", source="upstream_code", ref=f"{GRIDWORLD}:88-102"),
        Fact("An episode ends after 41 steps: the step count is incremented and done becomes true when the count "
             "is greater than 40", source="upstream_code", ref=f"{GRIDWORLD}:104-115"),
        Fact("The reward is the negative sum of squared differences between the achieved and desired flattened "
             "observations", source="upstream_code", ref=f"{GRIDWORLD}:176-177"),
        Fact("The achieved observation image is 1 at the agent cell and 0.2 at each in-bounds diagonal neighbour",
             source="upstream_code", ref=f"{GRIDWORLD}:128-138"),
        Fact("The desired observation image is 0.2 at every in-bounds cell of the goal's 3 x 3 neighbourhood and "
             "1 at the goal cell itself", source="upstream_code", ref=f"{GRIDWORLD}:140-151"),
        Fact("The step info carries success 0, the step count and the done flag", source="upstream_code",
             ref=f"{GRIDWORLD}:113-125"),
    ]
    safe_state = ("the simulation stops advancing: no step or reset is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the grid state is kept and stays readable")
    #: The fidelity contract of the model as deployed (spec 05-fidelity section 2).
    fidelity = {
        "engine": "custom:multiworld:GoalGridworld-v0",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "the fake backend seeds Python's random.Random from reset(seed); one seed and one action "
                     "sequence repeat the state hashes.  Upstream reset() takes no seed and draws from the global "
                     "numpy generator (goal_gridworld.py:71), so this seed control is a property of the fake, not "
                     "of the upstream class",
        },
        "timestep_ms": 0.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "event-driven analytic grid model: one tick is one move on a 10 x 10 grid, so timestep_ms is 0 and "
            "there are no dynamics, forces, contacts, actuator, sensor or noise models",
            "no wall-clock pacing: realtime_factor 0, only step commands advance the episode",
            "the fake re-implements the upstream class in pure Python and was not compared with the upstream "
            "environment; it uses Python's random.Random for the reset, upstream uses the unseeded global numpy "
            "generator",
            "no rendering: the upstream render() method needs OpenCV and writes a PNG outside the package, so the "
            "fake omits render and the observation grid is the only visual output",
        ],
    }
