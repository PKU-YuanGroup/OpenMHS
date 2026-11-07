"""OpenMHS driver for gh.jbakams/slimebot-volleyball: the 1-vs-1 VolleyBotEnv (a Gymnasium family driver).

The upstream environment is the legacy ``gym.Env`` subclass ``VolleyBotEnv`` in
``slimebot-volleyball/1_vs_1/environments/volleybot.py:679``.  It is a simulator: a 3D slime-volleyball game
whose physics comes from slimevolleygym and whose optional Webots view is only a visualization.  The device is
simulated (R0), so there is no hardware backend, no e-stop path to a machine and no operator-required limit.

A GymnasiumDriver is configuration only.  The bridge derives the contract from the environment's spaces:
``cap.world.step.v1`` takes ``{ticks, action}`` with ``action.values`` a five-element binary array from
``spaces.MultiBinary(5)`` (volleybot.py:744), ``cap.world.reset.v1`` takes ``{seed, options}`` and
``cap.world.seed.v1`` ``{seed}``.  ``VolleyBotEnv`` is not registered with ``gym.envs.registration`` and the clone
cannot be imported by this package, so only the package's ``fake`` backend is declared; there is no ``sim`` backend
that would call ``gym.make``.

The ``fake`` backend is a pure Python stand-in (fake.py): the gate environment has no gym, opencv or Webots
Supervisor module (numpy is present, but the upstream module also needs gym), and package code never imports the
clone.  The fake is a reduced model, not the upstream game; the ``fidelity`` gaps below name every reduction.  The
package is model-authored and unreviewed and
is checked on the fake backend only.

Every Fact cites a line of the clone at the pinned commit
0733b0ad1f9d1f62ba8b5717f69edf6b0cb1544a.  The fake's numbers are test data and never appear in these Facts.
"""

from mhs.driver import Fact, GymnasiumDriver

VOLLEYBOT = "slimebot-volleyball/1_vs_1/environments/volleybot.py"
TEAM_VOLLEYBOT = "slimebot-volleyball/2_vs_2/environments/team_volleybot.py"


class SlimebotVolleyball(GymnasiumDriver):
    device_id = "slimebot-volleyball"
    device_kind = "world.sim"
    mode = "simulated"
    risk = "R0"
    native = "environments.volleybot:VolleyBotEnv"
    backends = {"fake": ".fake:FakeVolleyBotEnv"}
    display_name = "Slimebot Volleyball 1-vs-1 (Gym simulation)"
    vendor, model = "jbakams", "Slimebot Volleyball 1-vs-1"
    tags = ["slimebot", "volleyball", "3d", "multiagent", "reinforcement-learning", "simulation", "gymnasium"]
    facts = [
        Fact("Slimebot-volleyball is a 3D version of slime volleyball, implemented on top of slimevolleygym and "
             "using Webots as a simulator for visualization", source="vendor_doc", ref="README.md:3"),
        Fact("The README calls the project a gym-like environment and says gym must be installed", source="vendor_doc",
             ref="README.md:26"),
        Fact("The README says the same physics as slimevolleygym is used, so the environment can run in a CMD "
             "without Webots", source="vendor_doc", ref="README.md:30"),
        Fact("The Webots Supervisor import is optional: outside Webots the import fails and WEBOTS_MODE is False",
             source="upstream_code", ref=f"{VOLLEYBOT}:24-29"),
        Fact("The game settings are TIMESTEP = 1/30 s, NUDGE = 0.1, FRICTION = 1.0, INIT_DELAY_FRAMES = 30, "
             "GRAVITY = -9.8*2*1.5 and MAXLIVES = 5", source="upstream_code", ref=f"{VOLLEYBOT}:36-41"),
        Fact("The non-pixel action space is spaces.MultiBinary(5) and the observation space is a Box with 18 values "
             "bounded by +-np.finfo(np.float32).max", source="upstream_code", ref=f"{VOLLEYBOT}:744-752"),
        Fact("The episode limit is t_limit = 3000", source="upstream_code", ref=f"{VOLLEYBOT}:732"),
        Fact("An episode is done when t reaches t_limit or when either agent's life is <= 0", source="upstream_code",
             ref=f"{VOLLEYBOT}:823-829"),
        Fact("The observation is [agent x, y, z, vx, vy, vz, ball x, y, z, vx, vy, vz, opponent x, y, z, vx, vy, vz] "
             "divided by 10.0", source="upstream_code", ref=f"{VOLLEYBOT}:369-374"),
        Fact("Action values 0 to 4 select forward, backward, jump, right and left when they are greater than 0",
             source="upstream_code", ref=f"{VOLLEYBOT}:420-455"),
        Fact("The caller's action controls agent_right and the baseline policy controls agent_left unless "
             "otherAction is supplied", source="upstream_code", ref=f"{VOLLEYBOT}:805-815"),
        Fact("Game.reset starts the ball at x=0, y=width/4-1.5, z=0 with vx uniform in [-20, 20], vy uniform in "
             "[10, 25] and vz uniform in [-10, 10]; the agents start at -width/4 and width/4 at height 1.5",
             source="upstream_code", ref=f"{VOLLEYBOT}:588-604"),
        Fact("A ball at the floor scores for the opposite side: checkEdges returns -1 when x <= 0 and 1 otherwise, "
             "and the game negates that for the right agent's reward", source="upstream_code",
             ref=f"{VOLLEYBOT}:225-235"),
        Fact("The README lists the observation shape as 18 for 1 vs 1 and 30 for 2 vs 2", source="vendor_doc",
             ref="README.md:39-40"),
        Fact("TeamVolleyBot uses the same MultiBinary(5) action space and a Box observation with 30 values",
             source="upstream_code", ref=f"{TEAM_VOLLEYBOT}:967-977"),
    ]
    safe_state = ("the simulation stops advancing: no step or reset is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the environment state is kept and stays readable")
    #: The fidelity contract of the reduced model as deployed (spec 05-fidelity section 2).  The bridge derives the
    #: engine, determinism kind and lockstep clock; the whole contract is written out here so it reads in one place.
    fidelity = {
        "engine": "slimebot-volleyball:VolleyBotEnv (1_vs_1)",
        "fidelity_level": "F1",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "reset(seed) reseeds the fake's Python random generator and its dynamics are deterministic, so "
                     "one implementation repeats a trajectory for the same seed and actions; the fake uses Python's "
                     "random.Random and a simplified collision model while the clone uses numpy's generator and its "
                     "own physics, so one seed does not give the same trajectory as the clone",
        },
        "timestep_ms": 1000.0 / 30.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "reduced physics: the fake models gravity, the five binary actions, wall bounces and the floor-contact "
            "score, but not the curved fence, agent/ball collision impulses, friction, the delay screen or the "
            "baseline policy's motion",
            "the fake uses Python's random.Random(seed) and returns Python float lists; the clone uses numpy's "
            "generator and numpy float arrays, so a seed does not reproduce the clone's trajectory",
            "the baseline opponent is static on the left half instead of BaselinePolicy; the observation order and "
            "the /10.0 scaling follow RelativeState.getObservation",
            "reset options are accepted by the family bridge but have no effect in the fake",
            "no rendering, no Webots Supervisor, no pixel observations and no 2-vs-2 TeamVolleyBot (30 values)",
            "the fake was not compared with an upstream run: the gate environment has no gym, opencv or Webots "
            "module (numpy is present, but the clone also needs gym), and only the family contract is checked",
            "the episode ends at t_limit 3000 or when a side loses 5 lives; scoring and lives are reduced to the "
            "floor-contact rule",
        ],
    }
