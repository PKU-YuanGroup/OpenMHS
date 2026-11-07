"""Hardware backend: opens the upstream ``ur_interface.ur:UR`` object for a Universal Robots arm.

Used only with ``backend="hardware"`` and ``allow_hardware=True`` after a human review.  This package is
model-authored and unreviewed and is R2, so the loader refuses its hardware backend until ``reviewed_by`` is signed
in ``driver.lock.json``; the acceptance gate runs the fake backend and never imports this module or the upstream
package.

``hostname`` is required (``UR`` raises TypeError for an empty one, src/ur_interface/ur.py:92-93).  Opening this
backend is neither a neutral connection nor a reset.  The upstream constructor opens ``UR_DASHBOARD``, whose
constructor connects, waits 3 s and runs ``initialize()`` (src/ur_interface/ur_dashboard.py:36-40); that unlocks a
protective stop, closes the safety popup and restarts safety whenever the safety status lacks NORMAL (the
emergency-stop states included), switches a MANUAL operational mode to automatic, brake-releases an arm in
POWER_OFF, BOOTING, POWER_ON or IDLE, and calls itself again until the arm runs
(src/ur_interface/ur_dashboard.py:96-134).  The constructor then opens the URX connection, sets the TCP to
``tcp_pose`` and samples the joints (src/ur_interface/ur.py:107-118).  The loader opens the backend when the
endpoint starts, so every start, a restart with a restored latch included, may power the arm, release its brakes
and clear safety states before any further operator action; the operator who starts the hardware view must have
the arm in sight and the physical e-stop in reach.  The remaining keyword options (``tcp_pose``, ``base_reference_frame``,
``resource_client``, ``resource_owner``, ``tool_resource_id``, ``logger``) are passed through to ``UR``; none is
invented here.  Every dashboard command prints its answer to stdout (src/ur_interface/ur_dashboard.py:78-87), which
would corrupt an MHS server that talks over stdio.
"""


def connect(hostname, **options):
    from ur_interface.ur import UR

    return UR(hostname=hostname, **options)
