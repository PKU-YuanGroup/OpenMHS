#!/usr/bin/env python3
"""Fault-injection MCP proxy: apply a command, then lose its reply.

Usage::

    python3 lost_reply_proxy.py -- <real mhs.mcp argv...>

The proxy speaks newline-delimited JSON-RPC on stdio to the client and forwards
every frame to the real ``mhs.mcp`` child.  It swallows **one** ``tools/call``
whose arguments carry a ``command_id`` (the mutating capability call): the child
still executes it and writes the receipt, but the proxy keeps the process alive
and never returns that reply.  The client therefore sees a bounded timeout while
the physical effect has already happened -- the HOST-003 lost-reply scenario.
All other requests (initialize, tools/list, mhs__inspect, reads) pass through.
"""

from __future__ import annotations

import json
import subprocess
import sys


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if "--" not in args:
        sys.stderr.write("usage: lost_reply_proxy.py -- <mhs.mcp argv...>\n")
        return 2
    child_argv = args[args.index("--") + 1 :]
    if not child_argv:
        sys.stderr.write("lost_reply_proxy: no child command\n")
        return 2
    child = subprocess.Popen(
        child_argv,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        bufsize=0,
    )
    assert child.stdin is not None and child.stdout is not None
    swallowed = False
    try:
        while True:
            line = sys.stdin.buffer.readline()
            if not line:
                break
            try:
                message = json.loads(line)
            except (UnicodeDecodeError, json.JSONDecodeError):
                child.stdin.write(line)
                child.stdin.flush()
                continue
            child.stdin.write(line)
            child.stdin.flush()
            if not isinstance(message, dict) or "id" not in message:
                continue
            request_id = message.get("id")
            while True:
                reply_line = child.stdout.readline()
                if not reply_line:
                    return 0
                try:
                    reply = json.loads(reply_line)
                except (UnicodeDecodeError, json.JSONDecodeError):
                    continue
                if not isinstance(reply, dict):
                    continue
                if reply.get("id") != request_id:
                    sys.stdout.buffer.write(reply_line)
                    sys.stdout.buffer.flush()
                    continue
                params = message.get("params") or {}
                arguments = params.get("arguments") if isinstance(params, dict) else None
                lose = (
                    not swallowed
                    and message.get("method") == "tools/call"
                    and isinstance(arguments, dict)
                    and bool(arguments.get("command_id"))
                )
                if lose:
                    swallowed = True
                    sys.stderr.write(
                        "lost_reply_proxy: swallowed tools/call reply for "
                        f"command_id={arguments.get('command_id')}\n"
                    )
                    sys.stderr.flush()
                    # Deliberately do not write the reply.  Stay alive so the
                    # caller observes a timeout, not a clean EOF.
                else:
                    sys.stdout.buffer.write(reply_line)
                    sys.stdout.buffer.flush()
                break
    finally:
        try:
            child.terminate()
            child.wait(timeout=3)
        except Exception:  # noqa: BLE001
            try:
                child.kill()
            except Exception:  # noqa: BLE001
                pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
