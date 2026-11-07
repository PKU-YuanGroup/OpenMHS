"""Hardware backend: opens the arm's dashboard connection through the SDK's own transport class.

Used only with backend="hardware" and allow_hardware=True (an operator decision).  This package is model-authored and
unreviewed, and it is R2, so the loader refuses its hardware backend until a human signs ``reviewed_by`` in
driver.lock.json.  The acceptance gate runs the fake backend and never imports this module or the dobot_sdk package;
nothing here ran on an arm.

The upstream ``DobotConnection`` opens a TCP socket to the dashboard port when ``connect()`` is called
(dobot_sdk/core/connection.py:171-215); the port 29999 is the dashboard command port
(dobot_sdk/api/robot.py:35-40, assets/SDK_API文档_完整版.md:99-108).  The driver's own ``setup()`` then sends
``RequestControl()``, the step every upstream example does before it moves (dobot_sdk/api/robot_control.py:22-34).
"""

DASHBOARD_PORT = 29999
#: The receive bound the upstream connection class starts with, in seconds (dobot_sdk/core/connection.py:48-49).
RECEIVE_TIMEOUT_S = 10.0


def connect(ip=None, port=DASHBOARD_PORT, **options):
    """Open the dashboard connection to ``ip`` and return it as the driver's native object."""
    if not ip:
        raise ValueError("the hardware backend needs the arm's IP address (option 'ip')")
    from dobot_sdk.core.connection import DobotConnection

    connection = DobotConnection(ip, port, **options)
    connection.set_timeout(None, RECEIVE_TIMEOUT_S)
    connection.connect()
    return connection
