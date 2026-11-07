"""Hardware backend: opens a Cozmo robot through the upstream Wi-Fi client.

Used only with backend="hardware" and allow_hardware=True (an operator decision).  This package is model-authored
and unreviewed (driver.lock.json reviewed_by is null): check it before it drives a robot.  The acceptance gate runs
the fake backend and never imports this module or the pycozmo package; nothing here ran on a robot.

The client talks to the robot over UDP at the address the clone defaults to, ``("172.31.1.1", 5551)``, the robot's
Wi-Fi access point (pycozmo/conn.py:37, 359), and the README opens it with Client(), start(), connect() and
wait_for_robot() (README.md:35-43).  Option ``robot_addr`` is a ``(host, port)`` pair for a robot at another address;
the other options go to the Client constructor: protocol_log_messages, auto_initialize, enable_animations and
enable_procedural_face (pycozmo/client.py:44-49).
"""


def connect(robot_addr=None, **options):
    """Open the robot and return the connected upstream Client object."""
    from pycozmo.client import Client

    client = Client(robot_addr=robot_addr, **options)
    client.start()
    client.connect()
    client.wait_for_robot()
    return client
