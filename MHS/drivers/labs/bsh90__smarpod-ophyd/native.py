"""Hardware backend: opens a SmarAct SmarPod through the vendor module ``smaract.smarpod``.

The gate never imports this module.  ``connect`` runs only when an operator loads the hardware backend with a human
``reviewed_by`` (this package is R2 and model-authored, so the loader refuses the hardware backend until then).  It
uses the same vendor calls as the upstream clone (src/SmarPodMain.py): ``Open``, ``SetSensorMode``, ``IsReferenced``,
``SetSpeed``, ``SetMaxFrequency``, ``Set_ui`` with ``PIVOT_MODE`` / ``PivotMode.RELATIVE``, ``SetPivot``,
``SetCoordinateSystem``, ``GetPose``, ``IsPoseReachable``, ``Move``, ``GetMoveStatus``, ``Stop`` and ``Close``.

The adapter deliberately does not run the upstream constructor's automatic ``set_up`` (src/OphydSmarPod.py:20): that
sequence calls ``Calibrate`` and, when the controller is not referenced, ``FindReferenceMarks``
(src/SmarPodMain.py:87-95), which move the platform without an MHS command and outside any operator envelope.  An
unreferenced controller is refused here, so referencing and calibration remain the site's vendor procedure.  The pose
read/write interface, the reachability check and the vendor stop are preserved.

``model`` and ``locator`` are required deployment options; the values in the upstream class (src/SmarPodMain.py:8-9)
are that author's controller, not a property of every SmarPod.  The concurrent call of ``Stop`` from the e-stop thread
while ``Move`` waits has not been verified against vendor documentation, so this backend remains unreviewed and never
runs from the acceptance gate or from an agent.
"""

import time

#: Implementation bound of the wait for MoveStatus.STOPPED after a command; it is not a device limit or a Fact.
STOP_TIMEOUT_S = 5.0


class SmarPodSignal:
    """The small runtime surface the driver uses, modelled on the upstream ``SmarSignal`` plus the vendor stop."""

    def __init__(self, handle, api):
        self._handle = handle
        self._api = api
        self._closed = False

    def get(self):
        pose = self._api.GetPose(self._handle)
        return [pose.positionX, pose.positionY, pose.positionZ,
                pose.rotationX, pose.rotationY, pose.rotationZ]

    def check_pose(self, pose):
        values = [float(item) for item in pose]
        if len(values) != 6:
            return False
        return bool(self._api.IsPoseReachable(self._handle, self._api.Pose(*values)))

    def set(self, pose):
        values = [float(item) for item in pose]
        if len(values) != 6:
            raise ValueError("a SmarPod pose needs six components")
        self._api.Move(self._handle, self._api.Pose(*values), 0, True)
        deadline = time.monotonic() + STOP_TIMEOUT_S
        while not self.get_status():
            if time.monotonic() >= deadline:
                raise RuntimeError("the controller did not report MoveStatus.STOPPED after Move")
            time.sleep(0.01)

    def get_status(self):
        return self._api.GetMoveStatus(self._handle) == self._api.MoveStatus.STOPPED

    def stop(self):
        self._api.Stop(self._handle)

    def tear_down(self):
        if not self._closed:
            self._api.Close(self._handle)
            self._closed = True


def connect(*, model, locator):
    """Open the controller and return the adapter; ``model`` and ``locator`` are operator options."""
    if isinstance(model, bool) or not isinstance(model, int):
        raise ValueError("model must be the integer controller model (for example 10052)")
    if not isinstance(locator, str) or not locator.strip():
        raise ValueError("locator must be the vendor locator string (for example 'usb:sn:MCS2-00006657')")
    from smaract import smarpod

    handle = smarpod.Open(model, locator)
    try:
        smarpod.SetSensorMode(handle, smarpod.SensorPowerMode.ENABLED)
        if not smarpod.IsReferenced(handle):
            raise RuntimeError("the controller is not referenced; run the vendor reference procedure before loading "
                               "this driver (automatic FindReferenceMarks is deliberately not performed)")
        # The configuration the upstream set_up applies (src/SmarPodMain.py:55-68, 123).
        smarpod.SetSpeed(handle, 1, 3e-3)
        smarpod.SetMaxFrequency(handle, 18500)
        smarpod.Set_ui(handle, smarpod.Property.PIVOT_MODE, smarpod.PivotMode.RELATIVE)
        smarpod.SetPivot(handle, [10e-3, 0, 0])
        smarpod.SetCoordinateSystem(handle, smarpod.Pose(0.0, 0.0, 0.0, 1.5, 0.0, 0.0))
    except BaseException:
        smarpod.Close(handle)
        raise
    return SmarPodSignal(handle, smarpod)
