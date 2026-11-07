OpenMHS is an independent open-source project, not affiliated with or endorsed by Anthropic, and not a reimplementation or compatible dialect of Anthropic's MHS research preview.

# Exemplar: gh.farama-foundation/gymnasium (a GymnasiumDriver family-config with a fidelity contract)

The CartPole-v1 environment (`gymnasium.envs.classic_control.cartpole:CartPoleEnv`) as a simulated R0 driver. A Gymnasium
driver is configuration only: `env_id = "CartPole-v1"` and the bridge derives the contract from the environment's spaces.
The package is model-authored (`driver.lock.json` `authored_by` kind `model`) and unreviewed (`reviewed_by` null). It is
checked on the **fake backend only**, and its evidence is `contract_checked`. A simulated R0 driver has no hardware
backend, so the review rule for R2 hardware does not apply to it.

## Run the gate

```sh
PYTHONPATH=MHS/sdk/src python3 -m mhs.driver check MHS/drivers/robots/farama-foundation__gymnasium --backend fake
```

It passes with five warnings that every Gymnasium family driver gets, because the schemas come from the bridge: `G6.NO_NATIVE_CALL`
for `cap.world.seed.v1` (the seed only sets the seed of the next reset, so it makes no native call) and four `G8.NO_UNIT` for the
integer inputs the bridge derives (`ticks`, `action.index`, `seed` twice). Declaring `actions` for `reset` and `seed` to add the
units was tried: it removes the two `seed` warnings but then exposes the reset inputs `scenario` and `options` without
descriptions and G6 and G8 fail, so the package leaves the warnings (a followup of `MHS/changes/WP-11.md`).

## Why a fake, and the gymnasium that was not run

Gymnasium is not importable where the gate runs (the upstream package needs Python 3.11 or newer and numpy, `pyproject.toml:11`
and `:27`), and package code never imports the clone. So `backends = {"fake": ".fake:FakeCartPoleEnv"}` is a pure Python
re-implementation of `CartPoleEnv` (the equations of `cartpole.py:165-227`) and of the 500-step `TimeLimit` that
`gymnasium.make("CartPole-v1")` adds (`gymnasium/envs/__init__.py:26-32`, `wrappers/common.py:130-134`). Every constant cites
its line. The card says `mock_strategy.preferred` is `upstream-sim`: on a machine with gymnasium installed, a backend name
that `backends` does not list (`--backend sim`) is served by `gymnasium.make("CartPole-v1")` (`GymnasiumDriver.open_native`);
**that path was not run here.**

## What it demonstrates

| Pattern | Where |
|---|---|
| A family member is class attributes only: `device_id`, `env_id`, `native`, `backends`, `tags`, `facts`, `safe_state`, `fidelity` | `driver.py` |
| The limits come from the environment, not from the driver: `Discrete(2)` gives `action.index` 0 to 1, and a refusal names the space | `cap.world.step.v1` |
| The fake copies the upstream space, so `action_space_ref` cites the line that defines it (`cartpole.py:151`): the derived bound is `upstream_code` with that ref, and G4 checks that the line shows it (`Discrete(2)` reads as the largest action, 1) | `driver.py`, `reference.json` |
| The full fidelity contract of a simulator: engine, level F1, determinism `seeded` with `seed_control` `parameter`, timestep 20 ms (`tau`), `realtime_factor` 0, clock `lockstep`, reset `full`, no snapshot, and `gaps` that say what is not modelled | `driver.py` `fidelity` |
| Facts that cite the equations, thresholds, spaces, reward and registration, one claim per cited range | `driver.py`, `facts.md` |
| A fake that mirrors the upstream class: the same parameters of `reset`, `step` and `__init__`, duck-typed `Discrete` and `Box` spaces for the bridge, and the physics constants of the clone | `fake.py` |
| Cases that check the physics by hand, the seed, the terminal state, the 500-step truncation, the reset options, the contract and the e-stop | `test_driver.py` |

## Files

| File | Role |
|---|---|
| `task.json` | the registry task card (input; a copy of `MHS/registry/tasks/robots/farama-foundation__gymnasium.json`) |
| `driver.py` | the `CartPole` GymnasiumDriver class |
| `fake.py` | `FakeCartPoleEnv` and the two space classes (gate G7 checks its members against `CartPoleEnv`) |
| `facts.md` | the facts and the contract with their sources |
| `test_driver.py` | the gate harness call plus cases for this driver |
| `driver.lock.json` | pinned upstream, install, backends, `authored_by`, `reviewed_by` |
| `reference.json`, `REFERENCE.md` | generated: `python3 -m mhs.driver reference <dir>` |
| `RESULT.json` | `pass` with the gate digest the check printed |

No `native.py` (a simulator has no hardware backend), no `site-limits.example.json` (the action space is the only bound and
there is nothing to narrow), no `fixtures/` (the synthesized inputs are in range).

## To serve another environment of the family

Change `env_id`, `native` (the entry symbol of the task card) and `facts`, and write the fake from that class. The five
classic-control symbols are in the card's `entry_symbols`; a MuJoCo-based environment needs its own model files (card `models`).

## Honest limits of this package

- **The fake was never compared with the upstream environment.** It uses `random.Random(seed)` for the initial state, upstream uses
  numpy's generator, so one seed gives different trajectories on the two; states and observations are Python floats, upstream
  returns a float32 array; there is no rendering and no `PassiveEnvChecker`. The first step from the zero state was checked by
  hand against `cartpole.py:170-190`, and a constant push ends the episode on step 9 of this fake; neither was compared with a
  real run. The fidelity `gaps` say all of this.
- **Level F1 is a claim about what is modelled** (the equations of motion of a cart and a pole, no contacts, friction, actuator,
  sensor or noise model), not about agreement with any device; nothing was validated.
- **`state_hash` counts episodes.** Two runs repeat a trajectory for one seed only from fresh worlds (the hash covers the
  episode number), which is how the determinism case of `test_driver.py` runs them.
- `check-report.json` is generated by every gate run (new timestamps each time) and is not part of the package. `RESULT.json`
  records the digest the check printed (`gate digest (RESULT.json gate.digest)`), which stays the same while the gate result stays the same.
