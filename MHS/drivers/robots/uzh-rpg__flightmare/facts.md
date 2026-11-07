OpenMHS is an independent open-source project, not affiliated with or endorsed by Anthropic, and not a reimplementation or compatible dialect of Anthropic's MHS research preview.

# Source facts for gh.uzh-rpg/flightmare

Pinned commit: `d4218aedac18cbe9364a0a0df10ab992c4b65e4f`. Source declarations and controlled fake results are not native execution.

| Fact | Source | Reference |
|---|---|---|
| FlightEnvVec is a Stable-Baselines VecEnv for the native vector environment. | upstream_code | `flightrl/rpg_baselines/envs/vec_env_wrapper.py:6` |
| FlightEnvVec builds a per-agent observation space Box(-inf, inf) with num_obs entries and a per-agent action space Box(-1, 1) with num_acts entries. | upstream_code | `flightrl/rpg_baselines/envs/vec_env_wrapper.py:13-19` |
| FlightEnvVec.seed delegates to the native wrapper's setSeed method. | upstream_code | `flightrl/rpg_baselines/envs/vec_env_wrapper.py:31-32` |
| FlightEnvVec.step calls the native batch step and returns copied observation, reward and done arrays plus a list of per-environment info dictionaries; on a done environment it adds an episode reward/length entry and clears that environment's reward history. | upstream_code | `flightrl/rpg_baselines/envs/vec_env_wrapper.py:34-55` |
| FlightEnvVec.reset calls the native reset and returns a copy of the batched observations. | upstream_code | `flightrl/rpg_baselines/envs/vec_env_wrapper.py:70-73` |
| FlightEnvVec.num_envs delegates to the native wrapper's getNumOfEnvs method. | upstream_code | `flightrl/rpg_baselines/envs/vec_env_wrapper.py:101-103` |
| The native VecEnv::step requires action, observation, reward and done matrices whose rows equal num_envs and calls perAgentStep for every environment. | upstream_code | `flightlib/src/envs/vec_env.cpp:80-104` |
| perAgentStep stores each environment's step reward and terminal flag, and when an environment is terminal it resets that environment and adds the terminal reward before the batch step returns. | upstream_code | `flightlib/src/envs/vec_env.cpp:144-162` |
| The pybind module exposes the vector environment as flightgym.QuadrotorEnv_v1 with reset, step, setSeed, close, getNumOfEnvs, getObsDim, getActDim and getExtraInfoNames. | upstream_code | `flightlib/src/wrapper/pybind_wrapper.cpp:16-33` |
| QuadrotorEnv declares 12 observations and 4 actions. | upstream_code | `flightlib/include/flightlib/envs/quadrotor_env/quadrotor_env.hpp:24-39` |
| QuadrotorEnv::isTerminalState returns true, with terminal reward -0.02, when the position-z state is at most 0.02. | upstream_code | `flightlib/src/envs/quadrotor_env/quadrotor_env.cpp:142-149` |
| The pinned quadrotor environment configuration sets sim_dt to 0.02 s and max_t to 5.0 s; both are configuration defaults, not universal bounds. | upstream_code | `flightlib/configs/quadrotor_env.yaml:3-4` |
| EnvBase::setSeed calls std::srand(seed). | upstream_code | `flightlib/include/flightlib/envs/env_base.hpp:39` |
| The random generator used by the quadrotor reset is an mt19937 seeded from std::random_device at construction, so the wrapper's std::srand seed does not seed that generator. | upstream_code | `flightlib/include/flightlib/envs/env_base.hpp:62` |
| The flightros FlightPilot subscribes to flight_pilot/state_estimate (nav_msgs/Odometry) to update a rendering quadrotor. | upstream_code | `flightros/src/pilot/flight_pilot.cpp:41-42` |
| The flightros FlightPilot timer callback mainLoopCallback is empty; the node is not a trajectory or actuator server. | upstream_code | `flightros/src/pilot/flight_pilot.cpp:80-82` |

## Scope and unresolved admission

The complete four-action, one-environment scalar adapter and the native-shaped batched fake remain. The factory now owns raw construction until adapter acceptance; rejected count/property validation attempts close once. Combined validation/cleanup failures preserve both error objects at the factory and both messages through stock model derivation. See CONSTRUCTION-OWNERSHIP.md. This proves no native build, rendering owner, raw partial-constructor cleanup, RNG fidelity or bounded native close.
