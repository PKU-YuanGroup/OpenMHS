"""Hardware backend: opens the Wago valve controller through the upstream Modbus TCP client.

Used only with backend="hardware" and allow_hardware=True (an operator decision).  This package is
model-authored and unreviewed, and it is R2: the loader refuses its hardware backend until a human
signs ``reviewed_by`` in driver.lock.json (the loader does this at R2 and R3 only).  The acceptance
gate runs the fake backend and never imports this module or the fish_sorter package.

The backend option ``config`` is the upstream ``pneumatic_config`` mapping (or the whole shipped file,
whose top-level ``pneumatic_config`` key wraps it, pneumatic_config.json:2): the constructor of
``ValveController`` reads ``config['connect']['host']`` and ``config['connect']['port']``
(valve_controller.py:36-44) and the driver reads the register map and the function codes from
``native.config`` (valve_controller.py:25, 82 and 105).  Every key the driver uses is checked before
anything connects, so a missing key cannot surface for the first time inside an e-stop.  The shipped
example is ``fish_sorter/configs/hardware/pneumatic_config.json``; a site passes its own mapping.

Opening the controller only opens the Modbus TCP connection: ``ValveController.__init__`` writes no
register (valve_controller.py:13-28).  The upstream ``_connect`` does not check the result of the
client's ``connect()`` (valve_controller.py:46-51), so this factory refuses a controller whose socket
is not open (``is_socket_open``, the check the upstream uses at valve_controller.py:56).
"""

_REQUIRED = {
    "connect": ("host", "port"),
    "register": ("start_address", "draw_time_add_offset", "expel_time_add_offset", "func_add_offset",
                 "func_echo_add_offset"),
    "function_codes": ("press_off", "press_on", "vac_on", "vac_off", "func_idle"),
}


def _problems(config):
    if not isinstance(config, dict):
        return ["the 'config' option must be the pneumatic config mapping"]
    out = []
    for section, keys in _REQUIRED.items():
        values = config.get(section)
        if not isinstance(values, dict):
            out.append(f"config[{section!r}] is missing")
            continue
        for key in keys:
            value = values.get(key)
            if key == "host":
                if not isinstance(value, str) or not value:
                    out.append(f"config[{section!r}][{key!r}] must be a host name or address")
            elif isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 65535:
                out.append(f"config[{section!r}][{key!r}] must be an integer from 0 to 65535")
    return out


def connect(config=None, env="prod", **options):
    if options:
        raise ValueError(f"unknown hardware backend option(s): {sorted(options)}")
    if isinstance(config, dict) and isinstance(config.get("pneumatic_config"), dict):
        config = config["pneumatic_config"]
    problems = _problems(config)
    if problems:
        raise ValueError("the hardware backend needs the pneumatic config mapping as the 'config' option: "
                         + "; ".join(problems))

    from fish_sorter.hardware.valve_controller import ValveController

    controller = ValveController(config, env=env)
    client = getattr(controller, "valve", None)
    if client is None or not client.is_socket_open():
        controller.disconnect()
        raise ConnectionError("the Wago valve controller did not accept the Modbus TCP connection "
                              f"({config['connect']['host']}:{config['connect']['port']})")
    return controller
