"""OpenMHS simulator driver for gh.ut-amrl/socialgym2: the SocialGym2 environment (RosSocialEnv).

DEVIATION FROM THE CARD: the card names the ros family and the ``RosDriver`` helper, but the
upstream interface this repository defines is a PettingZoo ``ParallelEnv`` multi-agent
environment, not a rosbridge topic/service transport: ``RosSocialEnv(ParallelEnv, EzPickle)`` is
defined at ``src/environment/ros_social_gym.py:46``, with per-agent ``Discrete(2)`` action spaces
at line 168, ``reset`` at line 272 and ``step`` at line 348.  The ROS services it calls
(``utmrsStepper`` and ``utmrsReset``, ``src/environment/services/utmrs.py:62-66``) are the
simulator transport used *inside* the environment class; the primary control interface is the
environment step over a dict of agent actions.  The package therefore uses ``GymnasiumDriver``
and exposes the upstream's per-agent ``Discrete(2)`` spaces as a joint ``Dict``.  A ROS transport
driver would not preserve the environment-step interface and could not start the observer,
rewarder or simulator graph.

The fake backend (``fake.py``) is a pure-Python stand-in: it never imports the clone, ROS,
``ut_multirobot_sim``, PettingZoo or the upstream observer/rewarder.  The upstream environment
cannot be instantiated here (it starts a ROS node and roslaunch parent at
``src/environment/ros_social_gym.py:194-200`` and waits for simulator services).  Every fact
cites the pinned commit 09a84865b8e22c86dd16658f403b18c3bbc67572.  This package is model-authored
and unreviewed; it is checked on the fake backend only.
"""

from mhs.driver import Action, Fact, Field, GymnasiumDriver

from .adapter import ParallelBridge, STOP, UNSEEDED_RESET


class SocialGym2(GymnasiumDriver):
    device_id = "socialgym2"
    device_kind = "world.sim"
    mode = "simulated"
    risk = "R0"
    native = "environment.ros_social_gym:RosSocialEnv"
    backends = {"fake": ".fake:FakeSocialGym", "sim": ".sim:open_sim"}
    actions = {STOP: Action(name="fence", safe_state=True, description="Fence local calls; confirm idle only for the fake",
                            input={}, output={"idle": Field("boolean"), "scope": Field("string")}),
               UNSEEDED_RESET: Action(name="reset_unseeded", description="Reset the native scenario without claiming a seed",
                                      input={}, output={"observation": Field("object")})}
    action_space_ref = "src/environment/ros_social_gym.py:168"
    display_name = "SocialGym2 multi-agent social navigation simulator"
    vendor, model = "ut-amrl", "SocialGym2 RosSocialEnv"
    tags = ["ros", "simulation", "multi-agent", "social-navigation", "pettingzoo", "reinforcement-learning"]
    facts = [
        Fact("RosSocialEnv is a PettingZoo ParallelEnv for multi-agent social navigation, not a "
             "ROS transport class.", source="upstream_code", ref="src/environment/ros_social_gym.py:46-51"),
        Fact("The constructor's num_agents default is (3, 5); possible_agents is player_<index> for the "
             "maximum of that range.", source="upstream_code",
             ref="src/environment/ros_social_gym.py:80-81"),
        Fact("The constructor builds possible_agents and curr_num_agents from num_agents.",
             source="upstream_code", ref="src/environment/ros_social_gym.py:144-157"),
        Fact("Every possible agent's action space is spaces.Discrete(2).",
             source="upstream_code", ref="src/environment/ros_social_gym.py:168"),
        Fact("Every possible agent's observation space is Box(low=-9999, high=9999, "
             "shape=(len(observer),)).", source="upstream_code", ref="src/environment/ros_social_gym.py:169-171"),
        Fact("observation_space(agent) and action_space(agent) return the entries of those per-agent maps.",
             source="upstream_code", ref="src/environment/ros_social_gym.py:223-227"),
        Fact("The constructor starts a ROS node and a roslaunch parent for launch_config, then creates "
             "the UTMRS service client and the SocialPips service proxy.",
             source="upstream_code", ref="src/environment/ros_social_gym.py:194-207"),
        Fact("UTMRS waits for and proxies the utmrsStepper and utmrsReset services.",
             source="upstream_code", ref="src/environment/services/utmrs.py:62-66"),
        Fact("reset(seed=None, return_info=True, options=None) resets the scenario, observer and "
             "rewarder, calls the simulator reset and a default step, and returns a dict of per-agent "
             "observations and a dict of infos.", source="upstream_code",
             ref="src/environment/ros_social_gym.py:272-346"),
        Fact("step(action_dict) copies each agent's discrete action into the action array sent to the "
             "UTMRS step together with x/y/angle velocity arrays and max speeds.",
             source="upstream_code", ref="src/environment/ros_social_gym.py:348-396"),
        Fact("step returns per-agent observation, reward, termination, truncation and info dicts.",
             source="upstream_code", ref="src/environment/ros_social_gym.py:447"),
        Fact("RosSocialEnv.seed(seed=None) is a no-op and close() is a no-op.",
             source="upstream_code", ref="src/environment/ros_social_gym.py:269-270"),
        Fact("RosSocialEnv.close does not shut down the launched simulator.",
             source="upstream_code", ref="src/environment/ros_social_gym.py:220-221"),
        Fact("ManualZoneEnv is a RosSocialEnv subclass and overrides sim_step to use the manual-zone "
             "response type.", source="upstream_code",
             ref="src/environment/environment_types/manual_zone.py:110"),
        Fact("ManualZoneEnv.sim_step calls the UTMRS step and converts it with its own response type.",
             source="upstream_code", ref="src/environment/environment_types/manual_zone.py:180-183"),
        Fact("The config runner wraps the environment with SuperSuit's pettingzoo_env_to_vec_env_v1 "
             "and concat_vec_envs_v1 before training.", source="upstream_code",
             ref="src/config_run.py:436-442"),
        Fact("The README describes the project as a multi-agent simulator for real world social "
             "navigation.", source="vendor_doc", ref="README.md:7"),
    ]
    safe_state = ("local adapter calls are fenced and idle; the real external simulator requires "
                  "independent stop confirmation, which is unavailable and never inferred from the fence")

    def make_bridge(self, native):
        if native is None:
            raise ValueError("an explicit raw ParallelEnv backend is required")
        return ParallelBridge(native, external=self.backend == "sim", device_id=self.device_id,
                              autoreset=self.autoreset, max_ticks=self.max_ticks,
                              action_space_ref=self.action_space_ref)

    #: The deployed artifact is a pure-Python recording/analytic fake, not the upstream simulator.
    #: The bridge derives the lockstep clock; no fixed timestep exists in the clone, so it is 0.
    fidelity = {
        "engine": "analytic:package fake (no physics)",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "the fake reseeds Python's random.Random on reset(seed); upstream seed() is a "
                     "no-op and the simulator's random stream is external, so a seed does not "
                     "reproduce an upstream trajectory",
        },
        "timestep_ms": 0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "the fake is pure Python: it runs no ROS node, no roslaunch, no UTMRS/pedsim process, no "
            "physics, no human agents and no observer or rewarder",
            "the upstream action interface is PettingZoo's per-agent action_space(agent) map; the "
            "shared adapter exposes one joint gymnasium Dict whose members copy the sourced Discrete(2) "
            "bounds, and the step input therefore requires every agent key at once",
            "the upstream observation width is len(observer), a runtime configuration; the fake "
            "returns a shorter placeholder vector of four values per agent and models no "
            "observation semantics",
            "upstream step returns per-agent reward, termination and truncation dicts; the bridge's "
            "scalar fields sum native rewards and complete only when all episode agents finish; per-agent maps stay in info",
            "the fake fixes the number of agents at a placeholder five, the maximum of the upstream "
            "constructor default (3, 5); num_agents is a deployment configuration",
            "reset and step state, rewards and observations are placeholder test data, not the "
            "simulator's scenario generation or dynamics",
            "the clone declares no fixed simulation timestep; the UTMRS simulator clock is external, "
            "so timestep_ms is 0 and the fake has no wall-clock pacing",
            "snapshot and restore are not offered: the upstream class exposes no get_state/set_state "
            "pair",
            "upstream seed() is a no-op; only the fake's Python generator is reseeded",
            "upstream close() is a no-op and does not stop the launched simulator; the fake has no "
            "external process to stop",
            "no hardware is modelled or contacted",
        ],
    }

    fidelity_by_backend = {
        "sim": {
            "engine": "SocialGym2 ROS/UTMRS (deployment blocked; adapter tested with controlled peers)",
            "fidelity_level": "F1", "determinism": {"kind": "none", "seed_control": "none",
                "notes": "upstream seed and reset seed are no-ops; no seeded replay claim"},
            "timestep_ms": 0, "clock": "external", "reset": "partial",
            "gaps": ["live factory refuses before ROS import because independent stop and owned lifecycle are missing",
                     "only source-shaped controlled raw peers tested; no real ROS, UTMRS or deployment validation",
                     "upstream terminal and truncation flags both use success_observation",
                     "one MHS tick is one native environment step; physics tick accounting remains unverified",
                     "no portable snapshot/restore or seeded replay"]}}
