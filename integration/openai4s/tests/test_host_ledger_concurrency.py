"""LEAD-HOST-LEDGER: one chain writer per normalized ledger path.

The default ``invoke()`` path is exercised with no injected ledger, through
independent ``HostLedger`` objects in threads and in separate local processes.
The assertions are on the durable chain: unique contiguous ``seq``, the
``prev_digest`` link, every completed call represented, and verification after a
reopen.  A corrupted chain must fail closed without rewriting a byte.
"""

from __future__ import annotations

import concurrent.futures
import json
import os
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

from openai4s_mhs.config import MHSConfig
from openai4s_mhs.host_evidence import HostLedger, HostLedgerError, verify_host_chain
from openai4s_mhs.mcp_invoke import invoke

from .hardware_endpoint import start_endpoint
from .host_remediation_support import REPO_ROOT
from .support import sdk_projection_available

CAPABILITY = "cap.world.step.v1"
LEDGER_CHILD = Path(__file__).with_name("ledger_child.py")


def _child_env() -> dict[str, str]:
    env = os.environ.copy()
    parts = [
        str(REPO_ROOT / "MHS/sdk/src"),
        str(REPO_ROOT / "work/openai4s-src"),
        str(REPO_ROOT / "integration/openai4s"),
    ]
    if env.get("PYTHONPATH"):
        parts.append(env["PYTHONPATH"])
    env["PYTHONPATH"] = os.pathsep.join(parts)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONUNBUFFERED"] = "1"
    return env


@unittest.skipUnless(sdk_projection_available(), "mhs.mcp / OpenAI4S MCP client not available")
class LedgerConcurrencyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory(prefix="mhs-host-ledger-")
        self.addCleanup(self.tmp.cleanup)
        self.directory = Path(self.tmp.name)
        self.endpoints = []
        for _ in range(4):
            endpoint = start_endpoint("conveyor", mode="simulated")
            self.addCleanup(endpoint.close)
            self.endpoints.append(endpoint)
        self.device_ids = [str(item.devices[0]["device_id"]) for item in self.endpoints]

    def _settings(self, name: str) -> Path:
        directory = self.directory / name
        directory.mkdir(parents=True, exist_ok=True)
        document = {
            "enabled": True,
            "allow_hardware": False,
            "endpoints": [
                {"id": f"e{index}", "url": endpoint.url, "label": f"e{index}"}
                for index, endpoint in enumerate(self.endpoints)
            ],
            "command_timeout_ms": 20000,
            "command_journal": str(directory / "commands.jsonl"),
            "host_ledger": str(directory / "host-ledger.jsonl"),
            "evidence_log": str(directory / "evidence.jsonl"),
        }
        path = directory / "settings.json"
        path.write_text(json.dumps(document, indent=2, sort_keys=True), encoding="utf-8")
        return path

    def _invoke(self, index: int, ticks: int) -> dict:
        return invoke(
            f"e{index}",
            self.device_ids[index],
            CAPABILITY,
            {"ticks": ticks},
            config=self.config,
        )

    def _assert_chain(self, path: Path, expected_outcomes: int) -> list[dict]:
        ledger = HostLedger(path)
        records = ledger.records()
        ledger.close()
        self.assertEqual([item["seq"] for item in records], list(range(len(records))))
        self.assertEqual(records[0]["kind"], "genesis")
        self.assertEqual(records[0]["seq"], 0)
        verification = verify_host_chain(records)
        self.assertTrue(verification["valid"], verification["errors"])
        self.assertTrue(HostLedger(path).verify()["valid"])
        outcomes = [item for item in records if item.get("outcome") == "receipt"]
        self.assertEqual(len(outcomes), expected_outcomes)
        for item in outcomes:
            self.assertEqual(item["status"], "completed")
        return records

    def test_concurrent_default_invoke_threads_keep_one_chain(self) -> None:
        self.config = MHSConfig.load(self._settings("threads"))
        ledger_path = Path(self.config.host_ledger_path)
        barrier = threading.Barrier(len(self.endpoints))
        real_append = HostLedger.append

        def synchronized(self, record, *, kind="record"):
            if kind == "invoke_intent":
                # All four calls have independently created their default
                # ledger and are about to append to the same path.
                barrier.wait(timeout=30)
            return real_append(self, record, kind=kind)

        with mock.patch.object(HostLedger, "append", synchronized):
            with concurrent.futures.ThreadPoolExecutor(len(self.endpoints)) as pool:
                futures = [
                    pool.submit(self._invoke, index, index + 1)
                    for index in range(len(self.endpoints))
                ]
                receipts = [future.result(timeout=120) for future in futures]

        self.assertTrue(all(receipt["status"] == "completed" for receipt in receipts))
        self.assertEqual(
            len({receipt["command_id"] for receipt in receipts}), len(self.endpoints)
        )
        for index, endpoint in enumerate(self.endpoints):
            self.assertEqual(endpoint.spec.bridges[self.device_ids[index]].sim.tick, index + 1)

        records = self._assert_chain(ledger_path, len(self.endpoints))
        command_ids = {receipt["command_id"] for receipt in receipts}
        intents = [item for item in records if item.get("outcome") == "intent"]
        outcomes = [item for item in records if item.get("outcome") == "receipt"]
        self.assertEqual({item["command_id"] for item in intents}, command_ids)
        self.assertEqual({item["command_id"] for item in outcomes}, command_ids)

    def test_concurrent_default_invoke_local_processes_keep_one_chain(self) -> None:
        self.config = MHSConfig.load(self._settings("processes"))
        ledger_path = Path(self.config.host_ledger_path)
        gate = self.directory / "processes" / "go"
        processes = []
        for index in range(len(self.endpoints)):
            processes.append(
                subprocess.Popen(
                    [
                        sys.executable,
                        "-B",
                        str(LEDGER_CHILD),
                        str(self.config.config_path),
                        f"e{index}",
                        self.device_ids[index],
                        CAPABILITY,
                        str(index + 1),
                        str(gate),
                    ],
                    env=_child_env(),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                )
            )
        gate.write_text("go\n", encoding="utf-8")
        results = []
        for process in processes:
            stdout, stderr = process.communicate(timeout=180)
            self.assertEqual(process.returncode, 0, stderr)
            results.append(json.loads(stdout.strip().splitlines()[-1]))
        self.assertTrue(all(item["status"] == "completed" for item in results))
        self.assertEqual(len({item["command_id"] for item in results}), len(self.endpoints))

        records = self._assert_chain(ledger_path, len(self.endpoints))
        command_ids = {item["command_id"] for item in results}
        self.assertEqual(
            {
                item["command_id"]
                for item in records
                if item.get("outcome") == "receipt"
            },
            command_ids,
        )

    def test_first_genesis_race_creates_exactly_one_anchor(self) -> None:
        path = self.directory / "genesis" / "ledger.jsonl"
        barrier = threading.Barrier(4)
        real_init = HostLedger.__init__

        def synchronized_init(self, *args, **kwargs):
            # Every instance is constructed on the empty path at the same time;
            # only one may write the genesis anchor.
            if args and str(args[0]) == str(path):
                barrier.wait(timeout=30)
            real_init(self, *args, **kwargs)

        with mock.patch.object(HostLedger, "__init__", synchronized_init):
            with concurrent.futures.ThreadPoolExecutor(4) as pool:
                ledgers = [
                    future.result(timeout=60)
                    for future in [pool.submit(HostLedger, path) for _ in range(4)]
                ]
        records = ledgers[0].records()
        self.assertEqual([item["seq"] for item in records], [0])
        self.assertEqual(sum(1 for item in records if item["kind"] == "genesis"), 1)
        self.assertTrue(HostLedger(path).verify()["valid"])

    def test_corrupt_chain_fails_closed_without_rewriting_bytes(self) -> None:
        path = self.directory / "corrupt" / "ledger.jsonl"
        HostLedger(path).close()
        live = HostLedger(path)
        live.append({"kind": "record", "n": 1})
        intact = path.read_bytes()

        # A torn tail (no newline) is not a chain that can be extended.
        with open(path, "ab") as handle:
            handle.write(b'{"kind":"record"')
        torn = path.read_bytes()
        with self.assertRaises(HostLedgerError) as caught:
            HostLedger(path)
        self.assertEqual(caught.exception.code, "MHS.EVIDENCE.CHAIN_BROKEN")
        with self.assertRaises(HostLedgerError):
            live.append({"kind": "record", "n": 2})
        self.assertEqual(path.read_bytes(), torn, "a failed open/append rewrote bytes")
        self.assertTrue(torn.startswith(intact))

        # A complete line whose digest no longer recomputes is equally fatal.
        tampered_path = self.directory / "tampered" / "ledger.jsonl"
        HostLedger(tampered_path).close()
        lines = tampered_path.read_text(encoding="utf-8").splitlines()
        record = json.loads(lines[0])
        record["kind"] = "genesis-tampered"
        lines[0] = json.dumps(record, sort_keys=True)
        tampered = ("\n".join(lines) + "\n").encode("utf-8")
        tampered_path.write_bytes(tampered)
        with self.assertRaises(HostLedgerError) as caught:
            HostLedger(tampered_path)
        self.assertEqual(caught.exception.code, "MHS.EVIDENCE.CHAIN_BROKEN")
        self.assertEqual(tampered_path.read_bytes(), tampered)


if __name__ == "__main__":
    unittest.main()
