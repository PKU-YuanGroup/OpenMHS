"""Explicit upstream simulator factory; never imported by the fake backend.

Pass upstream_root=<pinned repository root>. Its mujoco_ur_rl_ros2 directory
provides the top-level envs package; envs/__init__.py also imports sibling
environments and stable_baselines3. Required installed dependencies are numpy,
gymnasium, mujoco (with MjSpec) and stable_baselines3. The upstream Menagerie
lookup uses MUJOCO_MENAGERIE_PATH or ~/mujoco_menagerie; this factory changes
neither the environment nor the source files. No dependency is installed here.
"""

import hashlib
import importlib
import math
import os
from pathlib import Path
import sys
import threading


_PIN = "e58ea6178d8d8195beb92387ba365227840a96a9"
_SOURCE_HASHES = {
    "envs/__init__.py": "49a07a4b1aa9a2b6cb9eddc03df8d730f9314e2f880a3394a88f20652c132762",
    "envs/ur_reach_env.py": "cb986545be06ceb0c24ed35b82a0638a5329b0118d179525f38ff8257cb827e4",
    "envs/ur_pick_place_env.py": "8654ec0688e04fa9f30b00c8177d2e35046222e9e63216d48323d32a1ff2b7f8",
    "envs/ur_dual_arm_env.py": "0627ebe0b787c906763bd4c7a7ab06550f543cbff8493ccb2e31611fb4b19453",
    "envs/shared_arm_env.py": "3e0ffce2ac66073334e65ed7c8abf054fdd1aaa2a2efa1fb70b4fbfab753e709",
}
_IMPORT_LOCK = threading.Lock()


def make_env(*, upstream_root=None, render_mode=None):
    """Construct the pinned URReachEnv, or fail; never substitute a fake.

    render_mode is forwarded to the upstream constructor. Only None and human
    are supported: the pinned render() has no rgb_array implementation.
    """
    if upstream_root is None:
        raise ValueError("sim requires upstream_root pointing to the pinned repository root")
    if render_mode not in (None, "human"):
        raise ValueError("the pinned URReachEnv supports render_mode None or 'human', not rgb_array")
    source = Path(upstream_root).expanduser().resolve() / "mujoco_ur_rl_ros2"
    for relative, expected in _SOURCE_HASHES.items():
        path = source / relative
        if not path.is_file():
            raise FileNotFoundError(f"sim source is missing: {path}; expected repository pin {_PIN}")
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError(f"sim source differs from pin {_PIN}: {path}")
    menagerie = Path(os.environ.get("MUJOCO_MENAGERIE_PATH") or Path.home() / "mujoco_menagerie").expanduser()
    for relative in ("universal_robots_ur5e/ur5e.xml", "robotiq_2f85/2f85.xml"):
        if not (menagerie / relative).is_file():
            raise FileNotFoundError(f"sim asset is missing: {menagerie / relative}; configure MUJOCO_MENAGERIE_PATH")
    # The sibling imports use the absolute name envs.*, not the repository's
    # outer directory name. Cached foreign modules are rejected, never removed.
    with _IMPORT_LOCK:
        original_path = list(sys.path)
        sys.path.insert(0, str(source))
        try:
            package = importlib.import_module("envs")
            if Path(package.__file__).resolve() != source / "envs/__init__.py":
                raise RuntimeError("a different envs package is already loaded; use a fresh interpreter for this source")
            module = importlib.import_module("envs.ur_reach_env")
            if Path(module.__file__).resolve() != source / "envs/ur_reach_env.py":
                raise RuntimeError("a different envs.ur_reach_env module is loaded; use a fresh interpreter")
        except ImportError as exc:
            raise RuntimeError(
                "cannot import the pinned sim environment: install compatible numpy, gymnasium, mujoco and "
                f"stable_baselines3; missing/import-failing dependency: {exc}"
            ) from exc
        finally:
            sys.path[:] = original_path
    env = module.URReachEnv(render_mode=render_mode)
    try:
        physics_dt = float(env.model.opt.timestep)
        if not math.isfinite(physics_dt) or physics_dt <= 0:
            raise ValueError("MuJoCo model timestep must be positive and finite")
        # SDK Gymnasium fidelity reads public dt. Preserve upstream _dt (five
        # physics steps per env.step); report physics dt per FID-015.
        env.dt = physics_dt
    except Exception:
        env.close()
        raise
    return env
