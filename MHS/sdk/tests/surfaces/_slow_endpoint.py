"""A stdio conveyor endpoint whose ``cap.world.step.v1`` blocks (``verify-integration-surfaces/slow_ep.py``).

Run as a child process: ``python3 _slow_endpoint.py``; ``MHS_SLOW_STEP_S``
sets the delay (default 3 s).
"""

from __future__ import annotations

import os
import time
import warnings

from mhs.reference import build_endpoint, build_server


def main() -> None:
    delay = float(os.environ.get("MHS_SLOW_STEP_S", "3"))
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        spec = build_endpoint("conveyor")
        server = build_server(spec, log_ready=False)
    for device in server.devices.values():
        bridge = server._bridge(device)
        original = bridge.call

        def slow(capability_id, args=None, ctx=None, _original=original):
            if "world.step" in capability_id:
                time.sleep(delay)
            return _original(capability_id, args, ctx)

        bridge.call = slow
    server.run_stdio()


if __name__ == "__main__":
    main()
