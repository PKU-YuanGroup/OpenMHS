"""``python3 -m mhs.reference`` -- launch a reference endpoint (a protocol fixture, not a driver template).

Examples::

    python3 -m mhs.reference conveyor --port 7400
    python3 -m mhs.reference conveyor --stdio --test-profile
    python3 -m mhs.reference lab --port 7401
    python3 -m mhs.reference arm --port 7402 --noise --seed 42
    python3 -m mhs.reference replay --port 7403 --bundle evidence.json
"""

from __future__ import annotations

import argparse
import socket
import sys

from mhs.reference import ENDPOINTS, build_endpoint, serve


def _free_port(host: str) -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind((host, 0))
        return int(sock.getsockname()[1])


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python3 -m mhs.reference",
        description="Run one of the deterministic OpenMHS reference endpoints (protocol fixtures, not drivers).",
    )
    parser.add_argument("endpoint", choices=ENDPOINTS, help="reference endpoint to run")
    # --stdio takes precedence when both are given, so the documented
    # ``<name> --port 7400 --stdio`` invocation is accepted (stdio transport).
    parser.add_argument("--stdio", action="store_true", help="serve newline-delimited JSON-RPC on stdin/stdout (takes precedence over --port)")
    parser.add_argument("--port", type=int, default=None, help="serve loopback HTTP on this port (default 7400)")
    parser.add_argument("--host", default="127.0.0.1", help="HTTP bind address (loopback only by default)")
    parser.add_argument(
        "--endpoint-id",
        default=None,
        help="override the advertised endpoint id (default mhs://localhost:<port> or mhs://localhost/<name>)",
    )
    parser.add_argument(
        "--test-profile",
        action="store_true",
        help="conveyor only: expose x-cap.mhs-test.* fault-injection capabilities",
    )
    parser.add_argument("--noise", action="store_true", help="arm only: enable seeded pose noise")
    parser.add_argument("--seed", type=int, default=0, help="arm only: seed for seeded-noise/initial reset")
    parser.add_argument("--bundle", default=None, help="replay only: recorded evidence bundle to serve")
    parser.add_argument("--quiet", action="store_true", help="do not log to stderr")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    stdio = args.stdio
    host = args.host
    port = args.port
    if not stdio:
        port = 7400 if port is None else port
        if port == 0:
            port = _free_port(host)
    if args.endpoint_id:
        endpoint_id = args.endpoint_id
    elif stdio:
        endpoint_id = f"mhs://localhost/{args.endpoint}"
    else:
        endpoint_id = f"mhs://localhost:{port}"
    spec = build_endpoint(
        args.endpoint,
        endpoint_id=endpoint_id,
        test_profile=args.test_profile,
        bundle=args.bundle,
        noise=args.noise,
        seed=args.seed,
    )
    if not args.quiet:
        sys.stderr.write(
            f"[mhs.reference] {args.endpoint}: {len(spec.devices)} device(s), "
            f"profile={spec.profile}, transport={'stdio' if stdio else 'http'}\n"
        )
        sys.stderr.flush()
    try:
        serve(spec, host=host, port=None if stdio else port, stdio=stdio)
    except KeyboardInterrupt:  # pragma: no cover - interactive path
        pass
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
