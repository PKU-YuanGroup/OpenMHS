"""Backend-neutral receipts for native MoveAction request parameters.

This wrapper delegates to the production RosBridge and adds an explicitly
requested speed only after native terminal success. It does not invent a
sensor reading, alter native wire parameters, or intercept safety lifecycle.
"""

from copy import deepcopy


class GripperReceipts:
    def __init__(self, bridge):
        self._bridge = bridge

    def __getattr__(self, name):
        return getattr(self._bridge, name)

    def call(self, capability_id, args=None, ctx=None):
        submitted = deepcopy(args or {})
        output = self._bridge.call(capability_id, submitted, ctx)
        if capability_id == "x-cap.frankarobotics.move.v1":
            return {**output, "requested_speed_m_s": submitted["speed"]}
        return output
