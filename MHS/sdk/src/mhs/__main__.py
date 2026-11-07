"""``python3 -m mhs`` -- the ``mhs`` command (same as the ``mhs`` / ``openmhs`` console scripts).

* ``python3 -m mhs <command> ...`` -> the CLI (:mod:`mhs.cli`: ``serve``,
  ``driver``, ``validate``, ``describe``, ``estop``, ``run``, ``discover`` ...);
* ``python3 -m mhs conveyor|lab|arm|replay [flags]`` -> a reference endpoint
  (shorthand for ``python3 -m mhs.reference <name>``);
* ``python3 -m mhs mcp [flags]`` -> the MCP stdio projection (``python3 -m mhs.mcp``).
"""

from __future__ import annotations

import sys

_REFERENCE_NAMES = {"conveyor", "lab", "arm", "replay"}


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if args and args[0] in _REFERENCE_NAMES:
        from mhs.reference.__main__ import main as reference_main

        return reference_main(args)
    if args and args[0] in ("mcp", "serve-mcp"):
        from mhs.mcp import main as mcp_main

        return mcp_main(args[1:])
    from mhs.cli import main as cli_main

    return cli_main(args)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
