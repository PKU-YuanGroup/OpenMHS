"""Hardware backend: one BCS motor through the upstream ZeroMQ client.

Used only with ``backend="hardware"`` and ``allow_hardware=True`` (an operator decision).  The gate never imports this
module.  ``connect`` constructs the upstream ``bcsophyd.zmq.bcs_motor.BCSMotor`` (bcs_motor.py:21) and performs one
``GetMotorFull`` before the endpoint serves anything, so an unreachable server or an unknown motor name fails at load
time rather than on the first command.

The upstream package imports ``bcsophyd.zmq`` first, whose ``__init__.py`` imports ``BCSDeviceManager`` and therefore
``happi`` and ``pyzmq``; those are declared dependencies of the package (pyproject.toml).  This factory does not use the
device manager: its ``check_server_connection`` calls ``sys.exit(1)`` on failure (bcs_device_manager.py:137-151), which
would terminate the serving process.

The BCS protocol has no source-stated travel limit and the driver's move input is ``operator_required``.  A deployment
must supply the motor's configured unit and range through ``site-limits.json`` before any move is accepted.  The
upstream wrappers do not surface a failed MoveMotor/StopMotor exchange (bcs_motor.py:378-391, 412-426); the driver
therefore reads fresh GetMotorFull state, and a rejected stop is visible only through a later failed or unconfirmed
stop action.
"""


async def connect(host="127.0.0.1", port=5577, name="bcs_motor", original_name=None, units="",
                  timeout_s=60.0, settle_time_s=0.0):
    """Open the BCS connection for one motor and verify that GetMotorFull answers for it."""
    if not isinstance(name, str) or not name.isidentifier():
        raise ValueError("name must be a Python identifier (it names the ophyd Device)")
    if original_name is None:
        original_name = name
    if not isinstance(original_name, str) or not original_name.strip():
        raise ValueError("original_name must be the non-empty BCS motor name")
    if not isinstance(host, str) or not host.strip():
        raise ValueError("host must be the non-empty BCS server address")
    if isinstance(port, bool) or not isinstance(port, int) or not 1 <= port <= 65535:
        raise ValueError("port must be an integer in 1..65535")
    if not isinstance(units, str):
        raise ValueError("units must be the configured unit string (it may be empty)")
    if isinstance(timeout_s, bool) or not isinstance(timeout_s, (int, float)) or not timeout_s > 0:
        raise ValueError("timeout_s must be a positive number of seconds")
    if isinstance(settle_time_s, bool) or not isinstance(settle_time_s, (int, float)) or settle_time_s < 0:
        raise ValueError("settle_time_s must be a non-negative number of seconds")

    from bcsophyd.zmq.bcs_motor import BCSMotor

    motor = BCSMotor(
        name=name,
        originalName=original_name,
        itemType="motor",
        prefix="",
        units=units,
        bridgeIP=host,
        bridgePort=port,
        timeout=float(timeout_s),
        settle_time=float(settle_time_s),
    )
    # This connects the BCS ZeroMQ client (BCSServer.connect) and fails here if the server or the motor is unknown.
    data = await motor.zmq_get_motor_full_async(motor.originalName)
    if not data or not isinstance(data[0], dict) or "Raw Motor Position" not in data[0]:
        raise ValueError("GetMotorFull returned no Raw Motor Position for the requested motor")
    return motor
