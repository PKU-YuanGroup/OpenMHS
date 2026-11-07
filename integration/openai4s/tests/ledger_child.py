#!/usr/bin/env python3
"""One default-ledger governed invoke, started behind a cross-process gate.

Used by the concurrent default-``invoke`` regression: every child uses its own
``MHSConfig`` and the default ``HostLedger`` (nothing injected), and all point at
the same normalized ledger path.

Usage:
    python3 ledger_child.py SETTINGS ENDPOINT DEVICE CAPABILITY TICKS GATE_FILE
"""

from __future__ import annotations

import json
import os
import sys
import time

from openai4s_mhs.config import MHSConfig
from openai4s_mhs.mcp_invoke import invoke


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) != 6:
        sys.stderr.write(__doc__ or "")
        return 2
    settings, endpoint_id, device_id, capability_id, ticks, gate = args
    config = MHSConfig.load(settings)
    deadline = time.monotonic() + 30.0
    while not os.path.exists(gate):
        if time.monotonic() > deadline:
            sys.stderr.write("ledger_child: start gate never appeared\n")
            return 3
        time.sleep(0.01)
    receipt = invoke(
        endpoint_id,
        device_id,
        capability_id,
        {"ticks": int(ticks)},
        config=config,
        timeout_s=30.0,
    )
    print(
        json.dumps(
            {
                "status": receipt.get("status"),
                "command_id": receipt.get("command_id"),
                "pid": os.getpid(),
            },
            sort_keys=True,
        ),
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
