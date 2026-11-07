"""OpenMHS driver for gh.hogunkee/robocasa_g1: the RoboCasa-G1 tabletop simulation (GrootRoboCasaEnv).

The card proposes the ``GymnasiumDriver`` helper, but that bridge cannot publish this environment's contract.
``GrootRoboCasaEnv`` derives its action space from the robot key converter, which names every part action
``action.<part>`` (gymnasium_groot.py:66, robocasa/models/robots/__init__.py:233-238).  The gymnasium bridge prefixes
every ``Dict`` key with ``action.`` when it derives the limits, so it builds the unresolvable limit path
``action.action.left_arm`` and ``mhs.driver reference`` fails with "limit path 'action.action.left_arm' does not
resolve in the input schema".  The package is therefore a direct ``Driver`` over the card's first entry symbol.  The
MHS input names the five parts without the upstream ``action.`` prefix and the driver restores the prefix before the
native step; no upstream syntax was changed and the SDK was not edited (the minimal SDK repro is in RESULT.json).

The served task is the repository example: ``g1_unified/EvalPnPAppleToPlate_G1ArmsAndWaistDex31Hands_Env``
(test_env.py:17), the G1 arms-and-waist robot with Dex31 hands.  ``cap.world.step.v1`` takes ``ticks`` and one action
object (``left_hand``, ``right_hand``, ``left_arm``, ``right_arm``, ``waist``), every array element bounded -1..1
from the converter's ``Box(low=-1, high=1)``; ``cap.world.reset.v1`` takes ``seed`` and ``options`` and
``cap.world.seed.v1`` takes ``seed``.  The device is simulated (R1: simulation stepping, MHS/spec/04-safety.md) and
has no hardware backend, no physical e-stop path and no operator-required limit.

The gate does not install robosuite_g1, MuJoCo or the tabletop assets, and package code never imports the clone.  The
``fake`` backend is the package's pure Python F0 stand-in for the wrapper's public surface (reset, step, close); it
models no contacts, task success, controllers or camera and was never compared with the upstream environment.  No sim
or hardware backend is declared: that path needs robosuite_g1, MuJoCo, gymnasium and the assets, and was not run.

Every Fact cites a line of the clone at commit 6796d20bbee3fbe49e8f80a08f04bece07f481fd.  This package is
model-authored and unreviewed: it is checked on the fake backend only.
"""

from mhs import canonical
from mhs.driver import Driver, Fact, Field, Limit, action, estop, read, reset

BASIC = "robocasa/utils/gym_utils/gymnasium_basic.py"
GROOT = "robocasa/utils/gym_utils/gymnasium_groot.py"
CONVERTER = "robocasa/models/robots/__init__.py"
TABLETOP = "robocasa/environments/tabletop/tabletop.py"
EXAMPLE = "test_env.py"

#: The five part actions of G1ArmsAndWaistKeyConverter.unmap_action (robocasa/models/robots/__init__.py:402-410) and
#: their lengths in the repository example (test_env.py:25-33).
PARTS = (
    ("left_hand", 7),
    ("right_hand", 7),
    ("left_arm", 7),
    ("right_arm", 7),
    ("waist", 3),
)


def _action_limit():
    # robocasa/models/robots/__init__.py:236-238: every array action Box is low=-1, high=1.
    return Limit(min=-1, max=1, unit="1", source="upstream_code", ref=f"{CONVERTER}:229-240")


def _part_field(part, length):
    return Field("array", items="number", length=length, unit="1",
                 description=f"{part.replace('_', ' ').capitalize()} action", limit=_action_limit())


class RoboCasaG1(Driver):
    device_id = "robocasa-g1"
    device_kind = "world.sim"
    resource_id = "world"
    mode = "simulated"
    risk = "R1"
    native = "robocasa.utils.gym_utils.gymnasium_groot:GrootRoboCasaEnv"
    backends = {"fake": ".fake:FakeGrootRoboCasaEnv"}
    display_name = "RoboCasa-G1 G1 arms-and-waist tabletop environment (simulation)"
    vendor, model = "hogunkee", "RoboCasa-G1"
    tags = ["robocasa", "robosuite", "gymnasium", "tabletop", "manipulation", "humanoid", "unitree-g1",
            "simulation", "reinforcement-learning"]
    facts = [
        Fact("RoboCasaEnv is a Gymnasium environment (class RoboCasaEnv(gym.Env))", source="upstream_code",
             ref=f"{BASIC}:82"),
        Fact("The wrapper creates the underlying simulation with robosuite.make(**env_kwargs)", source="upstream_code",
             ref=f"{BASIC}:78"),
        Fact("The wrapper sets ignore_done=True when it builds the robosuite environment", source="upstream_code",
             ref=f"{BASIC}:69"),
        Fact("The action space is a Dict of per-part Box spaces with low -1 and high 1, plus a Discrete(2) base_mode "
             "for a hybrid mobile base", source="upstream_code", ref=f"{BASIC}:145-159"),
        Fact("step pops every per-part action from the dict, concatenates the per-robot arrays and asserts that no "
             "action key remains", source="upstream_code", ref=f"{BASIC}:235-250"),
        Fact("step returns the observation, reward, done, truncated=False and info", source="upstream_code",
             ref=f"{BASIC}:252-263"),
        Fact("reset calls np.random.seed(seed) before env.reset()", source="upstream_code", ref=f"{BASIC}:223-225"),
        Fact("reset returns the observation and info with success and grasp_distractor_obj set false",
             source="upstream_code", ref=f"{BASIC}:229-233"),
        Fact("get_basic_observation flips the image rows and casts every non-image observation to float32",
             source="upstream_code", ref=f"{BASIC}:196-209"),
        Fact("GrootRoboCasaEnv derives its observation space from the robot key converter and adds a Box(0, 255) of "
             "shape (256, 256, 3) for each mapped camera", source="upstream_code", ref=f"{GROOT}:26-37"),
        Fact("GrootRoboCasaEnv adds a Text annotation of at most 256 characters and derives its action space from "
             "the robot key converter", source="upstream_code", ref=f"{GROOT}:58-66"),
        Fact("get_groot_observation maps hand.* and body.* keys to state.* and raises ValueError for any other key",
             source="upstream_code", ref=f"{GROOT}:106-113"),
        Fact("GrootRoboCasaEnv.step unmaps the action, calls the parent step and maps the observation back",
             source="upstream_code", ref=f"{GROOT}:160-172"),
        Fact("The Groot observation uses annotation.human.coarse_action with an unlocked_waist prefix for "
             "G1ArmsAndWaist", source="upstream_code", ref=f"{GROOT}:147-150"),
        Fact("The G1 arms-and-waist converter maps left_hand, right_hand, left_arm, right_arm and waist, and "
             "unmap_action reads them as action.<part> keys", source="upstream_code", ref=f"{CONVERTER}:390-410"),
        Fact("The same converter configures the egoview, rs_view and worldview cameras at 1280 by 800",
             source="upstream_code", ref=f"{CONVERTER}:369-375"),
        Fact("deduce_action_space makes an integer action member a Discrete(2) and an array member a Box with low -1 "
             "and high 1 of the array length", source="upstream_code", ref=f"{CONVERTER}:229-240"),
        Fact("The repository example creates the environment id "
             "g1_unified/EvalPnPAppleToPlate_G1ArmsAndWaistDex31Hands_Env", source="upstream_code",
             ref=f"{EXAMPLE}:17"),
        Fact("The repository example steps the G1 arms-and-waist environment with action arrays of 7 (left and right "
             "hand), 7 (left and right arm) and 3 (waist) elements", source="upstream_code", ref=f"{EXAMPLE}:25-33"),
        Fact("The G1 arms-and-waist alias maps the robot class G1ArmsAndWaistDex31Hands to "
             "g1_arms_waist_dex31_hands", source="upstream_code", ref=f"{CONVERTER}:1052-1055"),
        Fact("make_key_converter selects G1ArmsAndWaistKeyConverter for the G1 arms-and-waist robot names",
             source="upstream_code", ref=f"{CONVERTER}:1110-1111"),
        Fact("The wrapper registers every registered robosuite environment for every Groot robot alias and adds "
             "g1_unified ids for the g1_arms_waist_dex31_hands alias", source="upstream_code",
             ref=f"{GROOT}:204-220"),
        Fact("Tabletop's constructor defaults control_freq to 20 Hz and horizon to 1000", source="upstream_code",
             ref=f"{TABLETOP}:294-295"),
        Fact("Tabletop forwards control_freq to the robosuite environment", source="upstream_code",
             ref=f"{TABLETOP}:399"),
        Fact("render returns the cached observation frame and refuses before a reset or step; close delegates to the "
             "inner environment", source="upstream_code", ref=f"{BASIC}:265-271"),
    ]
    safe_state = ("the simulation stops advancing: the e-stop closes the environment and no step or reset is accepted "
                  "until mhs.safety.reset clears the latch and reopens it at the recorded seed; the observation and "
                  "tick stay readable")
    #: The fidelity contract of the model as deployed (spec 05-fidelity FID-002).  Only the package fake is served, so
    #: the package claims F0: placeholder kinematic transitions, no contacts, no controllers, no MuJoCo and no camera.
    #: The Groot wrapper would be an F1 MuJoCo model with robosuite_g1, but that path is not installed or run here.
    fidelity = {
        "engine": "gymnasium:g1_unified/EvalPnPAppleToPlate_G1ArmsAndWaistDex31Hands_Env (kinematic fake stand-in)",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "the driver records a seed and passes it to GrootRoboCasaEnv.reset, which calls "
                     "np.random.seed(seed) before the robosuite reset (gymnasium_basic.py:223-225); the fake draws "
                     "its placeholder state with Python's random.Random, so one seed repeats on the fake but gives "
                     "different numbers than the upstream numpy stream, and no trajectory of the two was compared",
        },
        "timestep_ms": 50.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "no dynamics: the fake integrates a placeholder low-pass motion of five part arrays and has no MuJoCo, "
            "robosuite, rigid-body, contact, friction, controller, actuator, sensor or noise model; the upstream "
            "wrapper would be an F1 MuJoCo model, not this",
            "the fake always returns reward 0.0 and terminated/truncated False, mirroring the wrapper's "
            "ignore_done=True (gymnasium_basic.py:69) and truncated=False (gymnasium_basic.py:256); the concrete "
            "task's success test and reward are not modelled",
            "the fake returns 2x2x3 placeholder camera arrays for the four video.* keys whereas the observation space "
            "declares 256x256x3 (gymnasium_groot.py:20,29-30) and the cameras capture 1280x800 "
            "(robocasa/models/robots/__init__.py:374); the part state and action lengths follow the repository "
            "example (test_env.py:25-33) and are placeholders for the live controller dimensions",
            "the five action arrays are the G1ArmsAndWaist converter's part names from the repository example; the "
            "live action space is built from reconstruct_latest_actions(env) at runtime and the controller "
            "dimensions are not in this clone",
            "the fake draws the initial state with Python's random.Random and upstream with numpy's generator, so one "
            "seed gives different numbers on the two; reset without a seed reuses the recorded seed here while "
            "upstream np.random.seed(None) draws fresh entropy",
            "task scenes and objects need robosuite_g1, the tabletop assets and MuJoCo (README.md:29-42), which were "
            "not installed or downloaded here",
            "snapshot and restore are not offered: GrootRoboCasaEnv exposes no get_state/set_state pair",
            "no sim or hardware backend is declared; the real wrapper path needs robocasa imported to register the "
            "gym id, robosuite_g1, MuJoCo and the tabletop assets, and was not run",
            "no physical device is modelled and the simulator was never validated against one",
        ],
    }

    # ------------------------------------------------------------------ state
    def setup(self):
        observation, info = self.native.reset(seed=0)
        self._last_observation = observation
        self._last_reward = 0.0
        self._terminated = False
        self._truncated = False
        self._last_info = dict(info or {})
        self._tick = 0
        self._episode = 1
        self._seed = 0
        self._pending_seed = None

    def _state_hash(self):
        return canonical.digest({
            "observation": self._last_observation,
            "tick": self._tick,
            "episode": self._episode,
            "terminated": bool(self._terminated),
            "truncated": bool(self._truncated),
        })

    @read("observation", type="object", description="Last observation returned by the wrapper")
    def observation(self):
        return dict(self._last_observation)

    @read("reward", type="number", unit="1", description="Reward of the last step")
    def reward(self):
        return float(self._last_reward)

    @read("terminated", type="boolean", description="Whether the last step reported the task as done")
    def terminated(self):
        return bool(self._terminated)

    @read("truncated", type="boolean", description="Whether the last step reported a truncation")
    def truncated(self):
        return bool(self._truncated)

    @read("tick", type="integer", unit="1", description="Transitions applied since the last reset")
    def tick(self):
        return int(self._tick)

    @read("episode", type="integer", unit="1", description="Resets performed since the backend opened")
    def episode(self):
        return int(self._episode)

    @read("seed", type="integer", unit="1", description="Seed recorded for the last or next reset")
    def seed(self):
        return int(self._seed)

    @read("info", type="object", description="Info dictionary returned by the last reset or step")
    def info(self):
        return dict(self._last_info)

    # --------------------------------------------------------------- stopping
    @estop
    def stop(self):
        self.native.close()

    @reset
    def recover(self):
        observation, info = self.native.reset(seed=int(self._seed))
        self._last_observation = observation
        self._last_reward = 0.0
        self._terminated = False
        self._truncated = False
        self._last_info = dict(info or {})
        self._tick = 0
        self._episode += 1

    # ---------------------------------------------------------------- actions
    @action(cap="cap.world.step.v1",
            description="Advance the simulation",
            input={
                "action": Field("object", description="Per-part actions; upstream keys are action.<part>",
                                properties={part: _part_field(part, length) for part, length in PARTS}),
                "ticks": Field("integer", unit="1", description="Control steps"),
            })
    def step(self, action, ticks=1):
        native_action = {f"action.{part}": list(action[part]) for part, _length in PARTS}
        reward_total = 0.0
        for _ in range(int(ticks)):
            self.check_cancelled()
            observation, reward, terminated, truncated, info = self.native.step(native_action)
            self._last_observation = observation
            self._last_reward = float(reward)
            self._terminated = bool(terminated)
            self._truncated = bool(truncated)
            self._last_info = dict(info or {})
            reward_total += float(reward)
            self._tick += 1
            if self._terminated or self._truncated:
                break
        observation = dict(self._last_observation)
        return {
            "observation": observation,
            "reward": reward_total,
            "terminated": bool(self._terminated),
            "truncated": bool(self._truncated),
            "tick": int(self._tick),
            "state_hash": self._state_hash(),
        }

    @action(cap="cap.world.reset.v1",
            description="Reset the simulation",
            input={
                "seed": Field("integer", unit="1", description="Reset seed"),
                "options": Field("object", description="Reset options (accepted and ignored by the wrapper)"),
            })
    def reset_world(self, seed=None, options=None):
        chosen = seed if seed is not None else self._pending_seed
        self._pending_seed = None
        if chosen is None:
            chosen = self._seed
        kwargs = {"seed": int(chosen)}
        if options is not None:
            kwargs["options"] = dict(options)
        observation, info = self.native.reset(**kwargs)
        self._last_observation = observation
        self._last_reward = 0.0
        self._terminated = False
        self._truncated = False
        self._last_info = dict(info or {})
        self._tick = 0
        self._episode += 1
        self._seed = int(chosen)
        return {"observation": dict(observation), "seed": int(self._seed)}

    @action(cap="cap.world.seed.v1",
            description="Record the next reset seed",
            input={"seed": Field("integer", unit="1", description="Next reset seed")})
    def set_seed(self, seed):
        self._seed = int(seed)
        self._pending_seed = int(seed)
        return {"seed": int(seed), "accepted": True}
