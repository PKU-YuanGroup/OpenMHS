"""A stdio endpoint for the transport tests (run as a child process).

Usage::

    python3 _stdio_endpoint.py [--test-profile] [--slow-step-s SECONDS]

Serves the reference conveyor over stdio.  With ``--slow-step-s`` every
``cap.world.step.v1`` call first sleeps that long without looking at its
cancellation event (a non-cancellable blocking vendor call), which is the
fixture of the integration-surfaces review repro ``slow_test.py``.
"""

from __future__ import annotations

import argparse
import time

from mhs.reference import build_endpoint, build_server


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--test-profile", action="store_true")
    parser.add_argument("--slow-step-s", type=float, default=0.0)
    args = parser.parse_args()
    spec = build_endpoint("conveyor", endpoint_id="mhs://localhost/stdio-test",
                          test_profile=args.test_profile)
    server = build_server(spec, log_ready=False)
    if args.slow_step_s > 0:
        for device in server.devices.values():
            bridge = server._bridge(device)  # noqa: SLF001 - test fixture
            original = bridge.call

            def slow(capability_id, args_=None, ctx=None, _original=original):  # noqa: ANN001
                if capability_id == "cap.world.step.v1":
                    time.sleep(args.slow_step_s)
                return _original(capability_id, args_, ctx)

            bridge.call = slow
    server.run_stdio()


if __name__ == "__main__":
    main()
