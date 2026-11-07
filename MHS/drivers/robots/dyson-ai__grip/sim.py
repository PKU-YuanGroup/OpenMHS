"""Lazy factory for the selected pure-Python, non-realtime Panda environment."""
import importlib
import math


def configuration(options):
    allowed = {"seed", "sim_steps", "time_step"}
    if set(options) - allowed:
        raise ValueError("only seed, sim_steps and time_step are configurable; model/gripper/clock are fixed")
    value = {"seed": 77, "sim_steps": 10, "time_step": 1 / 240}
    value.update(options)
    if isinstance(value["seed"], bool) or not isinstance(value["seed"], int) or value["seed"] < 0:
        raise ValueError("seed must be a nonnegative integer")
    if isinstance(value["sim_steps"], bool) or not isinstance(value["sim_steps"], int) or value["sim_steps"] < 1:
        raise ValueError("sim_steps must be a positive integer")
    dt = value["time_step"]
    if isinstance(dt, bool) or not isinstance(dt, (int, float)) or not math.isfinite(dt) or dt <= 0:
        raise ValueError("time_step must be a positive finite number")
    return value


def _load_environment():
    return importlib.import_module("grip.environments.pick_and_place_env")


def open_sim(**options):
    config = configuration(options)  # validate before optional upstream import
    module = _load_environment()
    # TemplateEnvironment fixes real_time_sim=False. Explicit default avoids the
    # phase4 -> default fallback; fixed numeric control uses Panda finger distance.
    return module.PickAndPlaceEnvironment(**config, gripper="default", render_mode="DIRECT",
                                         enable_texture_randomiser=False)
