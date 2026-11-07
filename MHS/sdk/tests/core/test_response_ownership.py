"""Decoded public replies cannot mutate retained command or operation evidence."""
from __future__ import annotations

import copy
import unittest
from unittest.mock import patch

from mhs import canonical
from mhs.client import InProcessTransport, MHSClient
from mhs.evidence import verify_bundle
from tests.core import _device_server
from tests import test_ros_multi_image_artifacts as images


class ResponseOwnershipTests(unittest.TestCase):
    def make(self):
        server = _device_server.build_server()
        self.addCleanup(server.close)
        client = MHSClient(InProcessTransport(server))
        self.addCleanup(client.close)
        client.hello()
        device = next(iter(server.devices))
        client.open_session([device], capabilities=None, mode="simulated")
        return server, client, device

    def test_completed_output_replay_cannot_be_changed_by_previous_reply(self):
        _, client, device = self.make()
        key = canonical.ulid()
        first = client.invoke("cap.world.step.v1", {"ticks": 4}, device_id=device, command_id=key)
        self.assertEqual(first["status"], "completed", first)
        original = copy.deepcopy(first)
        first["output"]["tick"] = 999
        replay = client.invoke("cap.world.step.v1", {"ticks": 4}, device_id=device, command_id=key)
        self.assertTrue(replay["replayed"])
        self.assertEqual(replay["output"], original["output"])
        self.assertEqual(replay["receipt_id"], original["receipt_id"])
        self.assertEqual(client.read("world", device_id=device)["state"]["tick"], 4)
        replay["output"].clear()
        third = client.invoke("cap.world.step.v1", {"ticks": 4}, device_id=device, command_id=key)
        self.assertEqual(third["output"], original["output"])
        self.assertTrue(verify_bundle(client.export_evidence()).valid)

    def test_executed_failure_replay_cannot_be_changed_by_previous_reply(self):
        server, client, device = self.make()
        key = canonical.ulid()
        with patch.object(server.devices[device].bridge, "call", side_effect=RuntimeError("controlled bridge fault")):
            first = client.invoke("cap.world.step.v1", {"ticks": 4}, device_id=device, command_id=key)
        self.assertEqual(first["status"], "failed", first)
        original = copy.deepcopy(first["error"])
        first["error"].clear()
        replay = client.invoke("cap.world.step.v1", {"ticks": 4}, device_id=device, command_id=key)
        self.assertTrue(replay["replayed"])
        self.assertEqual(replay["error"], original)
        self.assertEqual(client.read("world", device_id=device)["state"]["tick"], 0)
        self.assertTrue(verify_bundle(client.export_evidence()).valid)

    def test_final_operation_reply_cannot_change_followup_get_or_command_replay(self):
        server, client, device = self.make()
        key = canonical.ulid()
        early = client.invoke("x-cap.test.long.v1", {"ms": 100}, device_id=device,
                              command_id=key, deadline_ms=1)
        self.assertIn("operation_id", early)
        self.assertTrue(server._operations[early["operation_id"]].done.wait(2))
        final = client.get_operation(early["operation_id"])
        self.assertEqual(final["status"], "completed", final)
        original = copy.deepcopy(final["output"])
        final["output"].clear()
        again = client.get_operation(early["operation_id"])
        self.assertEqual(again["output"], original)
        again["output"]["forged"] = True
        replay = client.invoke("x-cap.test.long.v1", {"ms": 100}, device_id=device, command_id=key)
        self.assertTrue(replay["replayed"])
        self.assertEqual(replay["output"], original)
        self.assertTrue(verify_bundle(client.export_evidence()).valid)

    def test_image_metadata_replay_and_stored_artifact_are_independent(self):
        fixture = images.RosMultiImageArtifactTests(
            "test_one_loaded_class_preserves_three_complete_planes_and_exact_headers")
        self.addCleanup(fixture.doCleanups)
        state, _, _, _, _, client, device = fixture.make(version=2)
        key = canonical.ulid()
        first = client.invoke("cap.sensing.image.v1", {"camera": "depth"},
                              device_id=device, command_id=key)
        self.assertEqual(first["status"], "completed", first)
        descriptor = copy.deepcopy(first["artifacts"][0])
        first["artifacts"][0]["x-vendor"].clear()
        replay = client.invoke("cap.sensing.image.v1", {"camera": "depth"},
                               device_id=device, command_id=key)
        self.assertTrue(replay["replayed"])
        self.assertEqual(replay["artifacts"], [descriptor])
        fetched = client.read_artifact(descriptor["uri"], session_id=first["session_id"])
        self.assertEqual(fetched["descriptor"], descriptor)
        self.assertEqual(state["subscriptions"], ["depth"])
        self.assertTrue(verify_bundle(client.export_evidence()).valid)


if __name__ == "__main__":
    unittest.main()
