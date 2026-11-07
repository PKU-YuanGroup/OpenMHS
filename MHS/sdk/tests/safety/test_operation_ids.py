"""Operation ids are full ULIDs and never collide (finding SDK-06).

Ports of ``sdk-core/e11.py`` (two commands started in the same millisecond got
the same ``op_`` + 20-character id, so one operation became unreachable) and
``sdk-core/e10.py`` (2000 commands left only ~1650 entries in the operation
table).
"""

from __future__ import annotations

import re
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import mhs.server as server_module
from mhs.server import Capability

from ._support import open_session, stub_capabilities, stub_server

FAST = "x-cap.test.fast.v1"
OPERATION_ID = re.compile(r"^op_[0-9A-HJKMNP-TV-Z]{26}$")


def _fast_server():
    caps = stub_capabilities(extra=[Capability(FAST, "axis",
                                               input_schema={"type": "object", "properties": {}})])
    return stub_server(capabilities=caps)


class OperationIdTests(unittest.TestCase):
    def test_e11_same_millisecond_commands_get_distinct_full_ulids(self) -> None:
        server, rpc, device, _bridge = _fast_server()
        session = open_session(rpc, device)
        for _attempt in range(20):
            barrier = threading.Barrier(2)
            results: dict[str, dict] = {}

            def go(key: str) -> None:
                barrier.wait()
                results[key] = rpc("mhs.command", session_id=session, capability_id=FAST, input={},
                                   deadline_ms=2000)

            threads = [threading.Thread(target=go, args=(key,)) for key in ("A", "B")]
            [thread.start() for thread in threads]
            [thread.join() for thread in threads]
            self.assertNotEqual(results["A"]["operation_id"], results["B"]["operation_id"])
            for receipt in results.values():
                self.assertRegex(receipt["operation_id"], OPERATION_ID)
                fetched = rpc("mhs.operations.get", session_id=session,
                              operation_id=receipt["operation_id"], deadline_ms=1000)
                self.assertEqual(fetched["command_id"], receipt["command_id"])

    def test_ten_thousand_concurrent_commands_get_ten_thousand_ids(self) -> None:
        server, rpc, device, _bridge = _fast_server()
        session = open_session(rpc, device)
        total = 10_000

        def one(_index: int) -> str:
            receipt = rpc("mhs.command", session_id=session, capability_id=FAST, input={},
                          deadline_ms=30000)
            if receipt.get("status") != "completed":
                raise AssertionError(receipt)
            return receipt["operation_id"]

        with ThreadPoolExecutor(max_workers=64) as pool:
            ids = list(pool.map(one, range(total)))
        self.assertEqual(len(set(ids)), total)
        self.assertEqual(len(server._operations), total)

    def test_an_id_collision_never_overwrites_a_registered_operation(self) -> None:
        server, rpc, device, _bridge = _fast_server()
        session = open_session(rpc, device)
        first = rpc("mhs.command", session_id=session, capability_id=FAST, input={}, deadline_ms=2000)
        original = server_module._new_operation_id
        self.addCleanup(setattr, server_module, "_new_operation_id", original)
        server_module._new_operation_id = lambda: first["operation_id"]
        second = rpc("mhs.command", session_id=session, capability_id=FAST, input={}, deadline_ms=2000)
        self.assertNotEqual(second["status"], "completed", second)
        self.assertEqual(server._operations[first["operation_id"]].command_id, first["command_id"])

    def test_no_truncated_ulid_ids_remain(self) -> None:
        source = Path(server_module.__file__).read_text(encoding="utf-8")
        self.assertNotIn("ulid()[:", source)


if __name__ == "__main__":
    unittest.main()
