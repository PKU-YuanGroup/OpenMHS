#!/usr/bin/env python3
"""Die between the real endpoint effect and the host's terminal journal record.

This is a real process exit (``os._exit``) in a separate interpreter, not an
in-process ``BaseException``: it proves that the durable ``dispatching`` marker
is what a *new* process reopens, and that the state is reconstructed as UNKNOWN
without any in-memory flag surviving.

Usage:
    python3 crash_after_effect.py SETTINGS ENDPOINT DEVICE CAPABILITY TICKS
"""

from __future__ import annotations

import os
import sys

from mhs.mcp import projection_tool_name
from openai4s_mhs import mcp_invoke as mi
from openai4s_mhs.config import MHSConfig


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) != 5:
        sys.stderr.write(__doc__ or "")
        return 2
    settings, endpoint_id, device_id, capability_id, ticks = args
    config = MHSConfig.load(settings)
    target_tool = projection_tool_name(device_id, capability_id)
    real_call = mi.MCPConnector.call

    def crash_after_effect(self, name, arguments=None):
        result = real_call(self, name, arguments)
        if name == target_tool:
            # The endpoint applied the effect; the reply is in hand; the host
            # has not written its terminal record yet.  No cleanup, no finally
            # blocks: this models process loss at exactly that boundary.
            os._exit(17)
        return result

    mi.MCPConnector.call = crash_after_effect
    mi.invoke(
        endpoint_id,
        device_id,
        capability_id,
        {"ticks": int(ticks)},
        config=config,
        timeout_s=10.0,
    )
    os._exit(18)  # unreachable: the patched call must fire for the command


if __name__ == "__main__":
    raise SystemExit(main())
