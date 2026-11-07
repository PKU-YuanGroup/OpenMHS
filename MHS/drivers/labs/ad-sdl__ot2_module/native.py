"""Hardware backend: opens the Opentrons OT-2 HTTP client of the pinned clone.

Used only with backend="hardware" after a human signs ``reviewed_by`` in driver.lock.json.  This package is
model-authored and R2, and the loader refuses the hardware backend of an unreviewed model-written package at R2
and R3.  The acceptance gate runs the fake backend and never imports this module or the ot2_interface package.

The factory builds the upstream OT2_Config and OT2_Driver.  The upstream constructor opens no persistent socket:
it probes ``/robot/lights`` with no timeout and raises RuntimeError when the robot does not answer HTTP 200
(src/ot2_interface/ot2_driver_http.py:70-77), and then switches the robot lights on, first off with a one-second
sleep when the probe does not report them off (:79-84).  Opening this backend therefore changes the robot's light
state; the constructor sends no other request and starts no run.  ``ip`` is required; ``port`` and the remaining
keyword options are passed to OT2_Config only when the deployment supplies them, so the clone's own defaults apply
otherwise (src/ot2_interface/config.py:48-54).  OT2_Config keeps unknown keywords (``extra=Extra.allow``,
src/ot2_interface/config.py:17), so a misspelled option is stored, not refused.  The install command in
driver.lock.json is how the deployment provides ``ot2_interface``; nothing here installs or starts it.
"""


def connect(ip=None, port=None, **options):
    """Build the upstream OT2_Driver for one robot.

    ``ip`` is the robot address (NODE_OT2_IP in the upstream node, README.md:13).  ``port`` and the other
    keywords are OT2_Config fields (src/ot2_interface/config.py:48-54); omit them to use the clone's defaults.
    """
    if not ip:
        raise ValueError("the OT-2 hardware backend needs the robot ip (OT2_Config.ip)")
    from ot2_interface.config import OT2_Config
    from ot2_interface.ot2_driver_http import OT2_Driver

    if port is None:
        config = OT2_Config(ip=ip, **options)
    else:
        config = OT2_Config(ip=ip, port=port, **options)
    return OT2_Driver(config)
