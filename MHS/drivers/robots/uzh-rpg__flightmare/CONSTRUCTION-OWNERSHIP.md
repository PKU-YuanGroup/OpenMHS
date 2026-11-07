OpenMHS is an independent open-source project, not affiliated with or endorsed by Anthropic, and not a reimplementation or compatible dialect of Anthropic's MHS research preview.

# Flightmare construction and validation boundary

The one-environment production adapter still preserves the complete four-action vector, batched native observations/rewards/done/info, explicit reset and seed policy. It continues to reject `num_envs != 1`; it does not invent actions for unselected environments or hide multi-environment outcomes.

The package factory owns the raw object until `VecEnvGymAdapter` is successfully returned to the SDK. If count validation or adapter construction raises, the factory attempts `raw.close()` exactly once before propagating the original error. If cleanup also raises, `AdapterCleanupError` retains both exception objects and chains the original validation failure. Its text includes both failures because the stock simulator model builder renders exception text and does not retain the exception chain. A cleanup exception remains visible at the stock loader boundary and is not reported as a successful close.

At pinned commit `d4218aedac18cbe9364a0a0df10ab992c4b65e4f`, `flightrl/rpg_baselines/envs/vec_env_wrapper.py:92-93` forwards close to the native wrapper. The controlled stock-loader tests check accepted construction, rejected multi-environment construction, a failure while reading `num_envs`, and a failed close. The exact independent two-environment reproducer is retained alongside the repaired result.

This repair does not establish ownership inside a raw constructor that raises before returning, native close latency or successful disposal by a built backend. The Python wrapper ignores the C++ step return, reset RNG is not seeded by the exposed `std::srand` route, and rendering/Unity ownership remains external. No native build, dependency installation, upstream import, simulator or hardware execution is claimed. The accepted scope, if independently approved, is the controlled fake contract and this finite production batch-boundary repair.
