"""OpenMHS driver for gh.uzh-rpg/flightmare: the FlightEnvVec reinforcement-learning world.

The card names ``RosDriver`` and a ``family:ros`` route, but the card's own
entry symbol is ``flightrl.rpg_baselines.envs.vec_env_wrapper:FlightEnvVec``
(vec_env_wrapper.py:6), a Stable-Baselines ``VecEnv`` around the pybind
``flightgym.QuadrotorEnv_v1`` vector environment (pybind_wrapper.cpp:16-33).
The flightros pilot is not a control server: it subscribes to an odometry
estimate to move a rendering quadrotor and its timer callback is empty
(flight_pilot.cpp:41-42,58-82).  ``GymnasiumDriver`` is therefore the matching
SDK helper; the deviation from the card is recorded in RESULT.json.

``FlightEnvVec`` is a *vector* environment: ``reset`` returns observations
shaped ``(num_envs, num_obs)``, ``step`` returns batched rewards and done
flags plus a per-environment info list, and the C++ ``VecEnv`` resets a done
environment inside the same step (vec_env_wrapper.py:34-73,
vec_env.cpp:144-162).  The stock Gymnasium bridge serves exactly one
environment and requires scalar reward and terminal values, so this package
contains a production adapter (``VecEnvGymAdapter``) that selects one explicit
environment index, checks the batch contract, and converts reward, done and
info per environment.  The fake in ``fake.py`` keeps the native vector shape
before that adaptation.

Scope: one environment (``num_envs == 1``).  A larger batch cannot be driven
through a scalar ``cap.world.step.v1`` action without hiding the actions and
outcomes of the other agents, so the adapter refuses it instead of reducing
the batch with a sum or an ``all``.  The real backend (a built ``flightgym``
extension plus a configured ``flightlib``) is not installed here; only the
package fake is exercised and no physical device exists.
"""

from mhs.driver import DriverDefinitionError, Fact, GymnasiumDriver


class AdapterCleanupError(RuntimeError):
    """Retain both failures, including text visible through model derivation."""

    def __init__(self, construction_error, cleanup_error):
        self.construction_error = construction_error
        self.cleanup_error = cleanup_error
        super().__init__(
            f"{type(construction_error).__name__}: {construction_error}; "
            f"raw cleanup also failed ({type(cleanup_error).__name__}: {cleanup_error})"
        )


class VecEnvGymAdapter:
    """Adapt one environment of a native ``FlightEnvVec`` batch to Gymnasium.

    The adapter is production code shared by the fake and a future real
    backend.  It preserves the native method names on the raw object and only
    converts the batch boundary:

    * ``action_space`` and ``observation_space`` are the upstream per-agent
      spaces (the wrapper builds them with one entry per action/observation,
      vec_env_wrapper.py:13-19);
    * ``reset`` calls the native ``seed`` (when supplied) and ``reset`` once
      and returns the observation of the selected environment;
    * ``step`` passes one action row to the native batch ``step`` and returns
      that environment's reward, terminal flag and info dictionary.

    ``num_envs`` must be 1.  Serving one row of a larger batch would require
    inventing actions for the others; refusing is the honest contract.
    """

    def __init__(self, raw, agent_index=0):
        count = getattr(raw, "num_envs", None)
        if isinstance(count, bool) or not isinstance(count, int) or count != 1:
            raise ValueError(
                "FlightEnvVec must be configured with num_envs == 1 for the scalar "
                f"MHS world interface; the native instance reports {count!r}"
            )
        if isinstance(agent_index, bool) or not isinstance(agent_index, int) or agent_index != 0:
            raise ValueError("the selected environment index must be 0 for a one-environment batch")
        self._raw = raw
        self._agent_index = agent_index

    # -- Gymnasium-shaped surface used by GymnasiumBridge ----------------------
    @property
    def action_space(self):
        return self._raw.action_space

    @property
    def observation_space(self):
        return self._raw.observation_space

    def seed(self, seed=None):
        if seed is not None:
            self._raw.seed(int(seed))

    def reset(self, seed=None, options=None):
        if options:
            raise ValueError("FlightEnvVec.reset() has no options argument; options must be empty")
        if seed is not None:
            self._raw.seed(int(seed))
        observation = self._raw.reset()
        return self._select(observation), {}

    def step(self, action):
        values = self._action_values(action)
        result = self._raw.step([values])
        if not isinstance(result, (tuple, list)) or len(result) != 4:
            raise ValueError("FlightEnvVec.step() must return (observation, reward, done, info)")
        observation, reward, done, info = result
        observation = self._select(observation)
        reward_value = float(self._select(reward))
        if reward_value != reward_value or reward_value in (float("inf"), float("-inf")):
            raise ValueError("FlightEnvVec.step() returned a non-finite reward")
        done_value = self._select(done)
        if isinstance(done_value, dict) or isinstance(done_value, (list, tuple)):
            raise ValueError("FlightEnvVec.step() returned a non-scalar done flag; a per-agent "
                             "completion mapping cannot be reduced to one scalar terminal value")
        terminal = bool(done_value)
        extra = self._select(info)
        if not isinstance(extra, dict):
            extra = {}
        return observation, reward_value, terminal, False, dict(extra)

    def close(self):
        self._raw.close()

    # -- explicit batch boundary ----------------------------------------------
    def _select(self, batch):
        """The selected environment's row of a native batch value."""
        try:
            return batch[self._agent_index]
        except (IndexError, KeyError, TypeError) as exc:
            raise ValueError("the native batch has no row for the selected environment") from exc

    def _action_values(self, action):
        values = action.tolist() if hasattr(action, "tolist") else list(action)
        if len(values) != len(self._raw.action_space.low):
            raise ValueError("the action does not match the native action dimension")
        return [float(value) for value in values]


class Flightmare(GymnasiumDriver):
    device_id = "flightmare-vecenv"
    device_kind = "world.sim"
    mode = "simulated"
    risk = "R0"
    native = "flightrl.rpg_baselines.envs.vec_env_wrapper:FlightEnvVec"
    backends = {"fake": ".fake:FakeFlightEnvVec"}
    display_name = "Flightmare vectorized quadrotor environment"
    vendor = "Robotics and Perception Group, University of Zurich"
    tags = ["flightmare", "flightlib", "flightgym", "quadrotor", "reinforcement learning", "simulation",
            "vector environment"]
    #: The fake copies the wrapper's per-agent Box(-1, 1) action space; this is
    #: the line that defines it, so the derived limits carry that provenance.
    action_space_ref = "flightrl/rpg_baselines/envs/vec_env_wrapper.py:16-19"
    #: The native VecEnv auto-resets a done environment inside the same step.
    #: A scalar Gymnasium episode therefore ends and the bridge refuses the next
    #: step until an explicit reset; the reset is a fresh native reset.
    autoreset = False
    facts = [
        Fact("FlightEnvVec is a Stable-Baselines VecEnv for the native vector environment.",
             source="upstream_code", ref="flightrl/rpg_baselines/envs/vec_env_wrapper.py:6"),
        Fact("FlightEnvVec builds a per-agent observation space Box(-inf, inf) with num_obs entries and a "
             "per-agent action space Box(-1, 1) with num_acts entries.",
             source="upstream_code", ref="flightrl/rpg_baselines/envs/vec_env_wrapper.py:13-19"),
        Fact("FlightEnvVec.seed delegates to the native wrapper's setSeed method.",
             source="upstream_code", ref="flightrl/rpg_baselines/envs/vec_env_wrapper.py:31-32"),
        Fact("FlightEnvVec.step calls the native batch step and returns copied observation, reward and done "
             "arrays plus a list of per-environment info dictionaries; on a done environment it adds an "
             "episode reward/length entry and clears that environment's reward history.",
             source="upstream_code", ref="flightrl/rpg_baselines/envs/vec_env_wrapper.py:34-55"),
        Fact("FlightEnvVec.reset calls the native reset and returns a copy of the batched observations.",
             source="upstream_code", ref="flightrl/rpg_baselines/envs/vec_env_wrapper.py:70-73"),
        Fact("FlightEnvVec.num_envs delegates to the native wrapper's getNumOfEnvs method.",
             source="upstream_code", ref="flightrl/rpg_baselines/envs/vec_env_wrapper.py:101-103"),
        Fact("The native VecEnv::step requires action, observation, reward and done matrices whose rows equal "
             "num_envs and calls perAgentStep for every environment.",
             source="upstream_code", ref="flightlib/src/envs/vec_env.cpp:80-104"),
        Fact("perAgentStep stores each environment's step reward and terminal flag, and when an environment is "
             "terminal it resets that environment and adds the terminal reward before the batch step returns.",
             source="upstream_code", ref="flightlib/src/envs/vec_env.cpp:144-162"),
        Fact("The pybind module exposes the vector environment as flightgym.QuadrotorEnv_v1 with reset, step, "
             "setSeed, close, getNumOfEnvs, getObsDim, getActDim and getExtraInfoNames.",
             source="upstream_code", ref="flightlib/src/wrapper/pybind_wrapper.cpp:16-33"),
        Fact("QuadrotorEnv declares 12 observations and 4 actions.",
             source="upstream_code", ref="flightlib/include/flightlib/envs/quadrotor_env/quadrotor_env.hpp:24-39"),
        Fact("QuadrotorEnv::isTerminalState returns true, with terminal reward -0.02, when the position-z state "
             "is at most 0.02.",
             source="upstream_code", ref="flightlib/src/envs/quadrotor_env/quadrotor_env.cpp:142-149"),
        Fact("The pinned quadrotor environment configuration sets sim_dt to 0.02 s and max_t to 5.0 s; both are "
             "configuration defaults, not universal bounds.",
             source="upstream_code", ref="flightlib/configs/quadrotor_env.yaml:3-4"),
        Fact("EnvBase::setSeed calls std::srand(seed).",
             source="upstream_code", ref="flightlib/include/flightlib/envs/env_base.hpp:39"),
        Fact("The random generator used by the quadrotor reset is an mt19937 seeded from std::random_device at "
             "construction, so the wrapper's std::srand seed does not seed that generator.",
             source="upstream_code", ref="flightlib/include/flightlib/envs/env_base.hpp:62"),
        Fact("The flightros FlightPilot subscribes to flight_pilot/state_estimate (nav_msgs/Odometry) to update "
             "a rendering quadrotor.",
             source="upstream_code", ref="flightros/src/pilot/flight_pilot.cpp:41-42"),
        Fact("The flightros FlightPilot timer callback mainLoopCallback is empty; the node is not a trajectory "
             "or actuator server.",
             source="upstream_code", ref="flightros/src/pilot/flight_pilot.cpp:80-82"),
    ]
    safe_state = ("the simulated world stops advancing: the runtime latches the e-stop and no world step, reset "
                  "or seed is accepted until an explicit safety reset clears the latch; no physical actuator or "
                  "hardware stop exists in this package")
    fidelity = {
        "engine": "analytic:vector-environment fake with no flightlib physics or Unity rendering",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "seeded",
            "seed_control": "reset_required",
            "notes": "the package fake seeds Python's random.Random from the supplied value; the upstream "
                     "EnvBase::setSeed only calls std::srand while reset draws from an mt19937 seeded from "
                     "std::random_device (env_base.hpp:39,62), so no upstream or bit-exact determinism is claimed",
        },
        "timestep_ms": 20.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "the fake is an analytic stand-in, not a recording: it integrates a placeholder altitude and "
            "observation from the action, with no flightlib rigid-body dynamics, no quadrotor model, no "
            "contacts, no sensors and no Unity rendering",
            "the fake uses the shipped QuadrotorEnv dimensions (12 observations, 4 actions) as placeholders; "
            "FlightEnvVec itself takes its dimensions from whatever pybind implementation it wraps",
            "20 ms is the pinned quadrotor_env.yaml sim_dt default and is configurable; the fake does not "
            "integrate that timestep, it only counts one environment step per bridge tick",
            "the adapter serves one environment (num_envs == 1); a larger native batch is refused rather than "
            "stepping the unselected rows with invented actions or reducing their rewards and terminations",
            "the native VecEnv auto-resets a done environment inside the same step and returns the post-reset "
            "observation; the adapter reports terminated and, with autoreset false, the bridge refuses the next "
            "step until an explicit reset (which resets the native environment again)",
            "the native seed path does not seed the mt19937 used by reset, so a live deployment cannot claim "
            "the seeded determinism that the fake implements for testing",
            "a real backend needs the flightgym pybind extension built from flightlib and a configured "
            "FLIGHTMARE_PATH; neither is installed here and no live simulator or hardware run was made",
            "the package exposes no image, point-cloud, camera or Unity render capability; only cap.world.step, "
            "cap.world.reset and cap.world.seed are bound",
        ],
    }

    def open_native(self):
        """Open the package backend and wrap the native batch in the production adapter."""
        raw = super().open_native()
        if raw is None:
            raise DriverDefinitionError(
                "the selected backend produced no FlightEnvVec object; a built flightgym extension and a "
                "configured flightlib are required for a live simulator backend",
                driver=type(self).__qualname__,
            )
        try:
            return VecEnvGymAdapter(raw)
        except BaseException as construction_error:
            # The SDK has not received the adapter and cannot yet own raw.
            # FlightEnvVec.close delegates to wrapper.close (upstream :92-93).
            # Model derivation renders exception text, so a cleanup failure
            # must be visible there as well as retained with the original.
            try:
                raw.close()
            except BaseException as cleanup_error:
                raise AdapterCleanupError(construction_error, cleanup_error) from construction_error
            raise
