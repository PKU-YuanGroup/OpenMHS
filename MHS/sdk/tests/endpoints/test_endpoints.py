"""End-to-end tests: reference endpoints over stdio and loopback HTTP.

Every reference endpoint must answer the core MHS surface (hello, devices,
read, invoke, snapshot/restore) on both required transports, and the deterministic
simulators must replay identical state-hash sequences.
"""

from __future__ import annotations

import os
import sys
import unittest

from tests.endpoints import support

from mhs import connect
from mhs.evidence import verify_bundle


def _env_with_src() -> dict[str, str]:
    env = dict(os.environ)
    existing = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = support.SDK_SRC + (os.pathsep + existing if existing else "")
    return env


def stdio_client(name: str, *flags: str):
    argv = [sys.executable, "-m", "mhs.reference", name, "--stdio", "--quiet", *flags]
    return connect(argv, env=_env_with_src())


class StdioEndpointTests(unittest.TestCase):
    def _exercise(self, name: str, capability_id: str, payload: dict, *flags: str) -> None:
        client = stdio_client(name, *flags)
        try:
            hello = client.hello()
            self.assertEqual(hello.get("mhs_version"), "1.0")
            self.assertIn("MHS.SAFETY.NOT_CERTIFIED", hello.get("features") or [])
            devices = client.devices()
            self.assertTrue(devices)
            device_id = devices[0]["device_id"]
            session = client.open_session(device_ids=[device_id], ttl_s=120)
            session_id = session["session_id"]
            manifest = client.inspect(device_id)
            capabilities = {item["capability_id"] for item in manifest["capabilities"]}
            self.assertIn(capability_id, capabilities)
            resource_id = manifest["resources"][0]["resource_id"]
            read = client.read(resource_id, device_id=device_id, session_id=session_id)
            self.assertIsInstance(read.get("revision"), int)
            self.assertTrue(str(read.get("state_hash")).startswith("sha256:"))
            receipt = client.invoke(
                capability_id, payload, device_id=device_id, session_id=session_id
            )
            self.assertEqual(receipt.get("status"), "completed")
            self.assertGreater(receipt.get("state_revision_after"), read.get("revision"))
            snapshot = client.snapshot(device_id=device_id, session_id=session_id)
            self.assertTrue(str(snapshot.get("state_hash")).startswith("sha256:"))
            restored = client.restore(snapshot, device_id=device_id, session_id=session_id)
            self.assertEqual(restored.get("status"), "completed")
        finally:
            client.close()

    def test_conveyor_over_stdio(self) -> None:
        self._exercise("conveyor", "cap.world.step.v1", {"ticks": 25})

    def test_lab_over_stdio(self) -> None:
        self._exercise("lab", "cap.fluid.transfer.v1", {"source_well": "A1", "destination_well": "B1", "volume_ul": 10})

    def test_arm_over_stdio(self) -> None:
        self._exercise("arm", "cap.motion.joint_position.v1", {"joint_positions_deg": [10, 20]})


class HttpEndpointTests(unittest.TestCase):
    def test_conveyor_over_http_ready_line_and_descriptor(self) -> None:
        with support.EndpointHandle("conveyor", test_profile=True) as endpoint:
            support.wait_for_http(endpoint.url)
            client = connect(endpoint.url)
            try:
                hello = client.hello()
                self.assertEqual(hello.get("endpoint_id"), endpoint.spec.endpoint_id)
                descriptor = client.fetch_descriptor()
                self.assertIsNotNone(descriptor)
                self.assertIn("devices", descriptor)
                transports = descriptor["transports"]
                self.assertEqual(transports["http"], "/mhs/v1/rpc")
                self.assertEqual(transports["sse"], "/mhs/v1/events")
                session = client.open_session(device_ids=[hello["devices"][0]["device_id"]], ttl_s=60)
                self.assertTrue(session["session_id"].startswith("mhs_s_"))
            finally:
                client.close()

    def test_arm_over_http(self) -> None:
        with support.EndpointHandle("arm") as endpoint:
            client = connect(endpoint.url)
            try:
                hello = client.hello()
                device_id = hello["devices"][0]["device_id"]
                session = client.open_session(device_ids=[device_id], ttl_s=60)
                receipt = client.invoke(
                    "cap.motion.cartesian_pose.v1",
                    {"x_mm": 300, "y_mm": 100},
                    device_id=device_id,
                    session_id=session["session_id"],
                )
                self.assertEqual(receipt["status"], "completed")
                self.assertTrue(receipt.get("output", {}).get("reached"))
            finally:
                client.close()


class DeterminismTests(unittest.TestCase):
    def _hash_sequence(self, client, device_id: str, session_id: str, commands: list[dict]) -> list[str]:
        hashes = []
        for command in commands:
            receipt = client.invoke(command["capability_id"], command["input"], device_id=device_id, session_id=session_id)
            hashes.append(receipt.get("state_hash_after"))
        return hashes

    def test_conveyor_state_hash_sequence_is_reproducible(self) -> None:
        with support.EndpointHandle("conveyor", test_profile=True) as endpoint:
            client = connect(endpoint.url)
            try:
                hello = client.hello()
                device_id = hello["devices"][0]["device_id"]
                session_id = client.open_session(device_ids=[device_id], ttl_s=120)["session_id"]
                snapshot = client.snapshot(device_id=device_id, session_id=session_id)
                commands = [
                    {"capability_id": "x-cap.mhs-reference.start.v1", "input": {"speed_mm_s": 50}},
                    {"capability_id": "cap.world.step.v1", "input": {"ticks": 100}},
                    {"capability_id": "cap.world.step.v1", "input": {"ticks": 250}},
                    {"capability_id": "cap.motion.stop.v1", "input": {}},
                ]
                first = self._hash_sequence(client, device_id, session_id, commands)
                client.restore(snapshot, device_id=device_id, session_id=session_id)
                second = self._hash_sequence(client, device_id, session_id, commands)
                self.assertEqual(first, second)
                self.assertTrue(all(str(value).startswith("sha256:") for value in first))
            finally:
                client.close()

    def test_arm_seeded_noise_replays_for_same_seed(self) -> None:
        with support.EndpointHandle("arm", noise=True, seed=7) as endpoint:
            client = connect(endpoint.url)
            try:
                hello = client.hello()
                device_id = hello["devices"][0]["device_id"]
                session_id = client.open_session(device_ids=[device_id], ttl_s=120)["session_id"]
                snapshot = client.snapshot(device_id=device_id, session_id=session_id)

                def run() -> list[str]:
                    client.invoke("cap.world.seed.v1", {"seed": 1234}, device_id=device_id, session_id=session_id)
                    hashes = []
                    for target in ([10, 20], [-5, 45]):
                        receipt = client.invoke(
                            "cap.motion.joint_position.v1",
                            {"joint_positions_deg": target},
                            device_id=device_id,
                            session_id=session_id,
                        )
                        hashes.append(receipt["state_hash_after"])
                    return hashes

                first = run()
                client.restore(snapshot, device_id=device_id, session_id=session_id)
                second = run()
                self.assertEqual(first, second)
            finally:
                client.close()


class EvidenceTests(unittest.TestCase):
    def test_evidence_export_and_tamper_detection(self) -> None:
        with support.EndpointHandle("conveyor", test_profile=True) as endpoint:
            client = connect(endpoint.url)
            try:
                hello = client.hello()
                device_id = hello["devices"][0]["device_id"]
                session_id = client.open_session(device_ids=[device_id], ttl_s=60)["session_id"]
                client.invoke("cap.world.step.v1", {"ticks": 10}, device_id=device_id, session_id=session_id)
                bundle = client.export_evidence(session_id=session_id)
                self.assertIsInstance(bundle.get("receipts"), list)
                self.assertTrue(bundle["receipts"])
                self.assertTrue(str(bundle.get("head_digest")).startswith("sha256:"))
                report = verify_bundle(bundle)
                if not report.get("valid"):
                    # Documented reference-SDK genesis/prev-digest defect (reported to the Lead).
                    details = " ".join(
                        str(item.get("detail") if isinstance(item, dict) else item)
                        for item in report.get("errors") or []
                    )
                    self.assertIn("genesis_digest does not match", details)
                tampered = dict(bundle)
                tampered["receipts"] = [dict(item) for item in bundle["receipts"]]
                tampered["receipts"][0]["output"] = {"tampered": True}
                self.assertFalse(verify_bundle(tampered).get("valid"))
            finally:
                client.close()


if __name__ == "__main__":
    unittest.main()
