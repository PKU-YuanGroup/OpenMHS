OpenMHS is independent and is not affiliated with, endorsed by, or a reimplementation of Anthropic's MHS research preview.

# Three gate fixes found by running simulator packages on their real upstream

On 2026-11-17 the gate was run with `--backend sim` over a pilot of 18 published simulator packages, each installed
from its pinned upstream commit in an isolated container (claude-opus-5-5, a model and not a human). Three SDK defects
stopped packages that had nothing wrong with them: a false `G3.GATE_TAMPERED` for every pybind11 extension, no way to
name the module that registers a Gymnasium environment, and a `G5.STALE` that no `mhs.driver reference` run could
clear. Each fix has a regression test that fails without it. None changes a fake-backend result: a re-gate of all 842
records in a worktree gives the same 750 gate passes with byte-identical digests, and the 92 non-passing records give
the same digests as unmodified `main` in that worktree.

## What changed

- **Builtins and `G3.GATE_TAMPERED`** (`mhs/driver/check.py`, `tests/driver/test_builtins_integrity.py`). pybind11
  extensions add private names to `builtins` on import; MuJoCo 3.8 adds `__MUJOCO_ERROR_FatalError`,
  `__MUJOCO_ERROR_UnexpectedError` and two struct lookups. The integrity snapshot fingerprinted each core module's
  `__builtins__` dict by content, so importing MuJoCo looked like a patched SDK. The snapshot now records each module's
  `__builtins__` by identity and every builtin by name and identity: an added name passes; a replaced or removed builtin
  (`builtins.open`, `builtins.__import__`) and a rebound module `__builtins__` are still tampering.
- **`GymnasiumDriver.env_module`** (`mhs/driver/families.py`, `mhs/bridge/gymnasium.py`,
  `tests/bridges/test_gym_env_module.py`). Environments registered at import time (`gym_pusht/PushT-v0`,
  `rware-tiny-1ag-v2`, `ur5-v0`) were not found by `gymnasium.make(env_id)`. A driver may now name that module
  (`env_module = "gym_pusht"`); the bridge imports it before `gymnasium.make`, only when it builds the environment itself
  (never for a `backends` entry such as the fake), and maps an import failure to `MHS.DEVICE.NOT_READY`. A value that is
  not a dotted module name is a definition problem. No published package sets it yet.
- **G5 on other backends** (`mhs/driver/check.py`, `tests/driver/test_g5_backend_reference.py`). The committed reference
  is the declared view over the default (fake) backend, which is what `python3 -m mhs.driver reference <dir>` writes. On
  `--backend sim`, G5 rendered it from the sim instance, so every package whose surface comes from its backend was
  stale. G5 now always compares with the default view and adds the warning `G5.BACKEND_SURFACE` with the JSON paths at
  which the live backend derives a different surface (for gym-pusht: the action limits), a fake/real parity signal for
  review.

## Evidence

SDK suite 3,945 tests OK (5 skipped), registry suite 376 OK. Pilot after the fixes: all 18 install; 3 pass on the real
simulator (farama-foundation/gymnasium, embomaster/polysim, kscalelabs/mujoco_playground; the last two failed only on
the builtins defect). Every result is `contract_checked` evidence from a gate run in a container, nothing more.
