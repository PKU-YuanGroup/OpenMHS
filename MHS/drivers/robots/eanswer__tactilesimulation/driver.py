"""OpenMHS driver for gh.eanswer/tactilesimulation: the TactilePush-v1 environment (a Gymnasium family driver).

A GymnasiumDriver is configuration only: ``env_id`` names the environment and the bridge derives the whole contract
from the environment's spaces.  ``cap.world.step.v1`` takes ``{ticks, action}`` with the action ``{values}`` bounded
element by element by the environment's three-dimensional ``Box(-1, 1)``; ``cap.world.reset.v1`` takes
``{seed, options}`` and ``cap.world.seed.v1`` ``{seed}``.  The device is simulated (R0): there is no hardware backend,
no e-stop path to a machine and no operator-required limit.

The upstream package needs DiffRedMax (``redmax_py``), numpy, scipy and torch, and the gate never imports the clone.
The ``fake`` backend is therefore the package's own pure Python TactilePush (fake.py); a backend name that ``backends``
does not list (``sim``) would be served by ``gym.make(env_id)`` (GymnasiumDriver.open_native), which needs the upstream
installation and was not run here (the fidelity gaps and RESULT.json record it).

The card lists four registered environments (StableGrasp-v1, TactilePush-v1, TactileRotation-v1 and Insertion-v3); one
Gymnasium family driver serves one ``env_id``, so this package covers TactilePush-v1 only.  The ``fidelity`` attribute
is the contract of the model as deployed (spec 05-fidelity FID-002); every constant and rule cites a line of the clone
at commit 0c42783a8b5cc7abe1a9fa3e6aa65e4aeb8eb670.  This package is model-authored and unreviewed: it is checked on
the fake backend only.
"""

from mhs.driver import Fact, GymnasiumDriver

PUSH = "envs/tactile_push_env.py"
BASE = "envs/redmax_torch_env.py"


class TactilePush(GymnasiumDriver):
    device_id = "tactile_push"
    env_id = "TactilePush-v1"
    native = "envs.tactile_push_env:TactilePushEnv"
    backends = {"fake": ".fake:FakeTactilePushEnv"}
    action_space_ref = f"{PUSH}:69-70"
    device_kind = "world.sim"
    mode = "simulated"
    risk = "R0"
    seed = 0
    #: The family bridge carries one observation value; this constructor option makes it the flat vector of
    #: envs/tactile_push_env.py:34-36 and :114-119 instead of the default tuple of tactile_map.
    env_kwargs = {"observation_type": "tactile_flatten"}
    display_name = "Tactile Simulation TactilePush-v1 (tactile pushing)"
    vendor, model = "eanswer", "TactilePush-v1"
    tags = ["tactile", "pushing", "reinforcement-learning", "simulation", "gymnasium", "differential-simulation"]
    facts = [
        Fact("TactilePush-v1 is registered with entry point envs.tactile_push_env:TactilePushEnv and "
             "max_episode_steps=100", source="upstream_code", ref="envs/__init__.py:9-13"),
        Fact("The constructor takes observation_type and defaults it to tactile_map", source="upstream_code",
             ref=f"{PUSH}:21"),
        Fact("In tactile_flatten mode the tactile observation is a 390-number vector and the state observation has "
             "3 numbers", source="upstream_code", ref=f"{PUSH}:34-36"),
        Fact("In tactile_flatten mode the observation is the state numbers followed by the tactile vector",
             source="upstream_code", ref=f"{PUSH}:114-119"),
        Fact("The state part of the observation is the goal position in the gripper frame (2 numbers) and the goal "
             "rotation relative to the gripper (1 number)", source="upstream_code", ref=f"{PUSH}:83-106"),
        Fact("The action space is a Box with low -1 and high 1 for each of 3 control inputs", source="upstream_code",
             ref=f"{PUSH}:69-70"),
        Fact("step applies tanh to the action and uses its first three components as the robot controls",
             source="upstream_code", ref=f"{PUSH}:174-182"),
        Fact("frame_skip is 5 and dt is sim.options.h multiplied by frame_skip", source="upstream_code",
             ref=f"{PUSH}:66-67"),
        Fact("The model integration timestep is 5e-3 s (5 ms)", source="upstream_code",
             ref="envs/assets/pusher/pusher.xml:2"),
        Fact("A reset sets state_q[1] to -0.001 and draws state_q[4] uniformly from -0.02 to 0.02",
             source="upstream_code", ref=f"{PUSH}:134-136"),
        Fact("A reset draws the goal x from 0.15 to 0.25, the goal y from -0.2 to 0.2, and the goal rotation "
             "uniformly from goal_y*pi - pi/16 to goal_y*pi + pi/16", source="upstream_code", ref=f"{PUSH}:143-146"),
        Fact("Every tenth step draws a random force probability uniformly from 0 to 1 and, when it is below 0.5, an "
             "external force uniformly from -1 to 1 on each axis, otherwise zero", source="upstream_code",
             ref=f"{PUSH}:184-193"),
        Fact("The reward is reward_pos + reward_rot + reward_touch + reward_action, built from the object-to-goal "
             "position and rotation errors, the contact variable difference and the squared action",
             source="upstream_code", ref=f"{PUSH}:202-211"),
        Fact("step returns the observation, the reward, False and an info object with the reward components and the "
             "final position and rotation errors", source="upstream_code", ref=f"{PUSH}:216-232"),
        Fact("The base class seeds with gym.utils.seeding.np_random and returns the seed as a list",
             source="upstream_code", ref=f"{BASE}:48-50"),
    ]
    safe_state = ("the simulation stops advancing: no step or reset is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the last state stays readable")
    fidelity_level = "F0"
    #: Fidelity contract of the deployed model (spec 05-fidelity section 2).  The upstream environment is a
    #: DiffRedMax rigid-body contact simulation (F1), but the delivered fake is an analytic kinematic stand-in with
    #: no dynamics, so the package declares F0 and discloses the difference in the gaps.
    fidelity = {
        "engine": "analytic:tactilesimulation/TactilePush-v1",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "reset(seed) or cap.world.seed.v1 fixes the random stream and the dynamics are deterministic, "
                     "so one implementation repeats a trajectory for the same seed and actions; this package's fake "
                     "draws with Python's random.Random and upstream with gym.utils.seeding.np_random, so a seed "
                     "gives different trajectories on the two",
        },
        "timestep_ms": 25.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "the deployed backend is a pure Python kinematic stand-in: it runs no force integration, rigid-body "
            "dynamics or contact model; the object and gripper move by placeholder gains of the tanh action and the "
            "sampled external force",
            "the upstream environment is a DiffRedMax rigid-body contact simulation of a pusher and an object on a "
            "plane (F1); this package declares F0 because the delivered fake is kinematic and was never compared "
            "with the upstream environment",
            "the driver selects observation_type tactile_flatten (envs/tactile_push_env.py:34-36 and :114-119) "
            "instead of the default tactile_map tuple, because the Gymnasium bridge carries one observation value; "
            "the flat observation is 3 state numbers followed by 390 tactile numbers",
            "the tactile observation is returned in its full 390-number shape but its values are placeholders and "
            "reward_touch is zero, not the upstream dense normal and shear force field",
            "the state observation carries the goal pose in the gripper frame only, as upstream does for the "
            "non-privilege observation types; the object pose is not part of it",
            "the fake uses Python's random.Random while upstream seeds numpy's generator through gym.utils.seeding, "
            "so one seed gives different draws and trajectories on the two",
            "one environment step applies frame_skip 5 at the 5 ms model timestep, i.e. 25 ms of simulated time; no "
            "wall-clock pacing is modelled and realtime_factor is 0",
            "snapshot and restore are not offered: the environment exposes no get_state or set_state",
            "no physical device is modelled and the model was never validated against one",
        ],
    }
