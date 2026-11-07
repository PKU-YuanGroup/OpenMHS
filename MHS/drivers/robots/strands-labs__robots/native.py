"""Hardware backend: construct the upstream Yahboom ROS 2 driver.

Used only with backend="hardware" and allow_hardware=True (an operator decision).  This package is model-authored and
unreviewed, and it is R2: the loader refuses its hardware backend until a human signs ``reviewed_by`` in
driver.lock.json (the loader does this at R2 and R3 only; an R1 package must not claim it).  The acceptance gate runs
the fake backend and never imports this module or ``strands_robots``; nothing here ran on a robot.

Options of the backend: ``transport`` is one of the upstream's ``"rosbridge"``, ``"ros2"`` or ``"twin"``
(strands_robots/drivers/yahboom_m3pro.py:26-42); ``port`` is the rosbridge ``host[:port]`` and is ignored by
``"ros2"``.  Every other keyword goes to the upstream ``YahboomM3ProDriver`` constructor.  The driver's own
``setup`` calls ``connect_eagerly``; it is idempotent, so the factory does not dial anything itself.
"""


def connect(transport="rosbridge", port=None, **options):
    from strands_robots.drivers.yahboom_m3pro import YahboomM3ProDriver

    return YahboomM3ProDriver(transport=transport, port=port, **options)
