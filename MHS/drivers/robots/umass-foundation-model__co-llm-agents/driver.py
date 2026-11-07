"""OpenMHS driver for gh.umass-foundation-model/co-llm-agents: the TDW-MAT ``transport_challenge_MA`` environment.

The repository is the code of an ICLR 2024 paper on cooperative embodied agents; its TDW-MAT subproject is a legacy
Gym task environment (``class TDW(Env)``) over the external ThreeDWorld simulator, registered as the gym id
``transport_challenge_MA`` with entry point ``tdw_gym:TDW``.  This is a GymnasiumDriver family member: the bridge
serves ``cap.world.step.v1``, ``cap.world.reset.v1`` and ``cap.world.seed.v1`` from the environment's spaces, and
the driver itself is class attributes only.  The device is simulated (R0): there is no hardware backend, no e-stop
path to a machine and no operator-required limit.

The environment is multi-agent: ``step`` receives ``{agent id: action}`` and each single-agent action is a Dict of
``type`` (Discrete(7)), ``object`` (Discrete(30)), ``arm`` (Discrete(2)) and ``message`` (plain text).  Upstream
builds ``self.action_space`` from the *observation* space by mistake, so this package serves the declared
single-agent action space (``action_space_single``) through the fake, which is what the bridge derives the contract
from.  The bridge derives limit paths as field names and cannot address an agent-id key such as ``"0"`` (the
``action.0.type`` path is refused), so the agent map stays inside the fake (it wraps the action under agent ``"0"``
for the default one-agent configuration) rather than in the contract.

The gate cannot install or run TDW (the upstream README needs Python 3.9, an editable install, a TDW build, an X
server and downloaded asset bundles), and package code never imports the clone.  The ``fake`` backend is therefore
a reduced analytic stand-in for ``TDW`` (F0), not the simulator; the fidelity ``gaps`` say what is not modelled and
which observations are smaller than the device's.  A backend name that ``backends`` does not list (``sim``) would
be served by ``gymnasium.make(env_id)``; that path needs the clone importable and the external TDW build and was
not run here (README.md).

This package is model-authored and unreviewed: it is checked on the fake backend only.
"""

from mhs.driver import Fact, GymnasiumDriver

TDW_GYM = "tdw_mat/tdw-gym/tdw_gym.py"
TDW_INIT = "tdw_mat/tdw-gym/__init__.py"
TDW_README = "tdw_mat/README.md"


class TDWTransportChallenge(GymnasiumDriver):
    device_id = "tdw-mat"
    device_kind = "world.sim"
    env_id = "transport_challenge_MA"
    native = "tdw_gym:TDW"
    backends = {"fake": ".fake:FakeTDW"}
    action_space_ref = f"{TDW_GYM}:104-108"
    display_name = "TDW-MAT transport_challenge_MA (ThreeDWorld multi-agent transport)"
    vendor, model = "UMass Foundation Model / CoELA", "ThreeDWorld Multi-Agent Transport"
    tags = ["gymnasium", "simulation", "multi-agent", "transport", "threedworld", "reinforcement-learning"]
    facts = [
        Fact("TDW-MAT extends the ThreeDWorld Transport Challenge into a multi-agent setting on top of the TDW "
             "platform", source="vendor_doc", ref=f"{TDW_README}:77"),
        Fact("The environment class is TDW, a subclass of the legacy Gym Env", source="upstream_code",
             ref=f"{TDW_GYM}:50"),
        Fact("gym id transport_challenge_MA is registered with entry point tdw_gym:TDW", source="upstream_code",
             ref=f"{TDW_INIT}:4-7"),
        Fact("The single-agent action space is a Dict of type Discrete(7), object Discrete(30), arm Discrete(2) and "
             "a message Text of at most 1000 characters", source="upstream_code", ref=f"{TDW_GYM}:104-108"),
        Fact("The action type 0 moves forward 0.5 m, 1 turns left 15 degrees, 2 turns right 15 degrees, 3 reaches "
             "for and grasps, 4 puts in a container, 5 drops and 6 sends a message; every other type asserts False",
             source="upstream_code", ref=f"{TDW_GYM}:628-644"),
        Fact("The single-agent observation space declares rgb (3, screen_size, screen_size), seg_mask "
             "(screen_size, screen_size, 3), depth (screen_size, screen_size), an agent pose Box(-30, 30, (6,)), "
             "two hand slots, 50 visible-object slots, status Discrete(4), valid Discrete(2), FOV Box(0, 120, "
             "(1,)), a 4x4 camera matrix, two message slots and current_frames Discrete(30)", source="upstream_code",
             ref=f"{TDW_GYM}:119-133"),
        Fact("action_space is built from observation_space_single, not from action_space_single: each agent id maps "
             "to the observation space", source="upstream_code", ref=f"{TDW_GYM}:139-140"),
        Fact("step compares action['arm'] with the strings left and right before it reaches the controller, while "
             "the declared arm space is Discrete(2)", source="upstream_code", ref=f"{TDW_GYM}:624-627"),
        Fact("reset takes keyword-only seed, options and output_dir; options must carry scene and layout and reset "
             "raises ValueError without it", source="upstream_code", ref=f"{TDW_GYM}:194-227"),
        Fact("reset launches the external ThreeDWorld build through TransportChallenge with launch_build",
             source="upstream_code", ref=f"{TDW_GYM}:211"),
        Fact("reset calls super().reset(seed=seed) and creates np.random.RandomState(seed) for the episode's "
             "randomness", source="upstream_code", ref=f"{TDW_GYM}:228-229"),
        Fact("step returns the legacy four-tuple (observation, reward, done, info)", source="upstream_code",
             ref=f"{TDW_GYM}:754"),
        Fact("reset returns (observation, info, env_api), a three-tuple", source="upstream_code",
             ref=f"{TDW_GYM}:346"),
        Fact("reward is reduced by 0.1 for each agent whose action status is neither success nor ongoing",
             source="upstream_code", ref=f"{TDW_GYM}:725-726"),
        Fact("done becomes True when num_frames reaches max_frame or the goal is achieved", source="upstream_code",
             ref=f"{TDW_GYM}:731"),
        Fact("screen_size is a constructor parameter with default 512 and max_frames has default 3000",
             source="upstream_code", ref=f"{TDW_GYM}:52"),
        Fact("reset opens ./dataset/room_types.json from the working directory", source="upstream_code",
             ref=f"{TDW_GYM}:312-313"),
        Fact("reset opens ./dataset/name_map.json from the working directory", source="upstream_code",
             ref=f"{TDW_GYM}:269"),
        Fact("TDW-MAT pins tdw==1.11.23.5", source="upstream_code", ref="tdw_mat/requirements.txt:17"),
        Fact("The setup uses Python 3.9 and an editable install", source="vendor_doc", ref=f"{TDW_README}:28-30"),
        Fact("The transport challenge asset bundles must be downloaded and unzipped under TDW_MAT",
             source="vendor_doc", ref=f"{TDW_README}:59"),
    ]
    safe_state = ("the simulation stops advancing: no step or reset is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the environment state is kept and stays readable")
    #: The model as deployed: the fake backend is analytic (F0) and not the ThreeDWorld engine.
    fidelity = {
        "engine": "gymnasium:transport_challenge_MA (reduced analytic stand-in; upstream is ThreeDWorld)",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "reset(seed=...) fixes the fake's object placement and the action sequence repeats a trajectory; "
                     "upstream seeds np.random.RandomState(seed) at reset (tdw_gym.py:229). The fake draws with "
                     "Python's random.Random, not numpy's generator, so one seed does not give the same trajectory "
                     "on the two implementations",
        },
        "timestep_ms": 0.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "no physics and no contacts: the fake is an analytic F0 stand-in that moves a point agent and tracks "
            "held object ids; the upstream environment advances the ThreeDWorld engine",
            "no fixed timestep: one cap.world.step.v1 tick is one upstream action decision, and the upstream "
            "controller advances a variable number of frames per action (info['num_frames_for_step'], "
            "tdw_gym.py:748); fidelity.timestep_ms is 0",
            "the fake returns 2x2 images (rgb 3x2x2, seg_mask 2x2x3, depth 2x2) instead of the upstream "
            "3 x screen_size x screen_size, screen_size x screen_size x 3 and screen_size x screen_size arrays "
            "(screen_size defaults to 512, tdw_gym.py:52), and its visible-object slots, camera matrix and object "
            "ids are placeholders; empty object and hand slots use -1, outside the declared Discrete range, "
            "because the bridge needs an integer where upstream pads with None",
            "the fake accepts a seed-only reset and supplies a placeholder scene; upstream reset requires options "
            "with scene and layout (tdw_gym.py:227) and reads ./dataset/name_map.json and "
            "./dataset/room_types.json from the working directory",
            "the fake corrects the action space: the contract is the declared single-agent action_space_single, "
            "while upstream builds action_space from observation_space_single (tdw_gym.py:139-140) and its step "
            "compares a string arm, not the declared Discrete(2) index (tdw_gym.py:624-627); the fake serves the "
            "default one-agent configuration and wraps the action under agent id 0 for TDW.step's agent map",
            "the fake uses Python random.Random, upstream uses numpy's np.random.RandomState; one seed gives "
            "different trajectories on the two",
            "the declared action field message is a Text space, which the bridge has no string kind for, so its "
            "published schema is an open object; the fake accepts a string and uses it for action type 6",
            "no rendering, no top-down images and no assets: the TDW build, the X server and the transport "
            "challenge asset bundles are not present",
        ],
    }
