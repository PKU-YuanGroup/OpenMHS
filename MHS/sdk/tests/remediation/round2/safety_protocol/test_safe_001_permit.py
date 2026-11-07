"""RE-SAFE-001: one single-use permit authorizes at most one effect.

The race test uses only a Python line trace as a scheduling barrier: both
requests are paused on entry to the production permit check, then released
together.  Production permit checks, the bridge and permit state are untouched.
"""
from __future__ import annotations

import sys
import threading
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from _fixtures import (  # noqa: E402
    at_function,
    command,
    error_code,
    issue_permit,
    make_device,
    make_server,
    open_session,
    result,
    status_of,
    thread_trace,
)

CAP = "cap.test.permit_action.v1"
PAYLOAD = {"gate": "divert"}


class PermitSingleUseTests(unittest.TestCase):
    def setUp(self) -> None:
        self.device, self.bridge = make_device("permit", with_aux=True)
        self.server = make_server(self.device)
        self.device_id = self.device.device_id
        self.session = open_session(self.server, [self.device_id])

    def _permit(self, payload: dict | None = None, **kwargs) -> str:
        payload = dict(payload or PAYLOAD)
        response = issue_permit(self.server, self.session, self.device_id, CAP, payload, **kwargs)
        self.assertIn("result", response, response)
        return result(response)["permit_id"]

    def _calls(self) -> int:
        return self.bridge.counts.get(CAP, 0)

    # -- required race ---------------------------------------------------
    def test_two_distinct_command_ids_share_one_permit_at_most_one_effect(self) -> None:
        permit_id = self._permit()
        barrier = threading.Barrier(2)
        outputs: dict[str, dict] = {}
        command_ids = {"first": "01J8ZQ3V6Y7M2N4P6R8S0T2V4A", "second": "01J8ZQ3V6Y7M2N4P6R8S0T2V4B"}

        def run(which: str) -> None:
            with thread_trace(at_function("_check_permit"), barrier, timeout=0.75):
                outputs[which] = command(
                    self.server, self.session, self.device_id, CAP, PAYLOAD,
                    command_id=command_ids[which], permit_id=permit_id, deadline_ms=1000,
                )

        threads = [threading.Thread(target=run, args=(name,), daemon=True)
                   for name in ("first", "second")]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(8.0)
        self.assertTrue(all(not thread.is_alive() for thread in threads), "requests did not finish")

        completed = [name for name, response in outputs.items() if status_of(response) == "completed"]
        self.assertEqual(len(completed), 1, outputs)
        other = next(name for name in outputs if name not in completed)
        self.assertEqual(status_of(outputs[other]), "rejected", outputs[other])
        self.assertIn(
            error_code(outputs[other]),
            {"MHS.SAFETY.PERMIT_INVALID", "MHS.DEVICE.BUSY"},
            outputs[other],
        )
        self.assertEqual(self._calls(), 1, self.bridge.calls)
        self.assertEqual(self.bridge.state["valve"], "divert")
        self.assertEqual(self.server._revisions[self.device_id], 1)

        # Later reuse of the consumed permit is refused and never re-executes.
        reuse = command(
            self.server, self.session, self.device_id, CAP, PAYLOAD,
            command_id="01J8ZQ3V6Y7M2N4P6R8S0T2V4C", permit_id=permit_id,
        )
        self.assertEqual(status_of(reuse), "rejected", reuse)
        self.assertEqual(error_code(reuse), "MHS.SAFETY.PERMIT_INVALID")
        self.assertEqual(self._calls(), 1)
        self.assertEqual(self.server._revisions[self.device_id], 1)

    # -- positive controls ----------------------------------------------
    def test_legal_first_use_and_same_id_replay_do_not_consume_twice(self) -> None:
        permit_id = self._permit()
        command_id = "01J8ZQ3V6Y7M2N4P6R8S0T2V5A"
        first = command(self.server, self.session, self.device_id, CAP, PAYLOAD,
                        command_id=command_id, permit_id=permit_id)
        self.assertEqual(status_of(first), "completed", first)
        self.assertFalse(result(first).get("replayed"))
        self.assertEqual(self._calls(), 1)
        self.assertEqual(self.server._revisions[self.device_id], 1)

        replay = command(self.server, self.session, self.device_id, CAP, PAYLOAD,
                         command_id=command_id, permit_id=permit_id)
        self.assertEqual(status_of(replay), "completed", replay)
        self.assertTrue(result(replay).get("replayed"), replay)
        self.assertEqual(result(replay)["receipt_id"], result(first)["receipt_id"])
        self.assertEqual(self._calls(), 1, "a same-id replay must not execute again")
        self.assertEqual(self.server._revisions[self.device_id], 1)

        second_use = command(self.server, self.session, self.device_id, CAP, PAYLOAD,
                             command_id="01J8ZQ3V6Y7M2N4P6R8S0T2V5B", permit_id=permit_id)
        self.assertEqual(status_of(second_use), "rejected", second_use)
        self.assertEqual(error_code(second_use), "MHS.SAFETY.PERMIT_INVALID")
        self.assertEqual(self._calls(), 1)

    def test_permit_bindings_still_reject_other_session_device_resource_digest_principal(self) -> None:
        permit_id = self._permit()
        other_session = open_session(self.server, [self.device_id], principal_id="agent:round2")

        second_device, _second_bridge = make_device("permit-b")
        self.server.devices[second_device.device_id] = second_device
        self.server._revisions[second_device.device_id] = 0
        self.server._device_locks[second_device.device_id] = threading.Lock()
        self.server._latched[second_device.device_id] = False
        both = open_session(self.server, [self.device_id, second_device.device_id])

        wrong_principal = open_session(self.server, [self.device_id], principal_id="agent:other")

        cases = {
            "other_session": command(self.server, other_session, self.device_id, CAP, PAYLOAD,
                                     command_id="01J8ZQ3V6Y7M2N4P6R8S0T2V6A", permit_id=permit_id),
            "other_device": command(self.server, both, second_device.device_id, CAP, PAYLOAD,
                                    command_id="01J8ZQ3V6Y7M2N4P6R8S0T2V6B", permit_id=permit_id),
            "other_resource": command(self.server, self.session, self.device_id, CAP, PAYLOAD,
                                      command_id="01J8ZQ3V6Y7M2N4P6R8S0T2V6C", permit_id=permit_id,
                                      resource="aux"),
            "other_digest": command(self.server, self.session, self.device_id, CAP, {"gate": "main"},
                                    command_id="01J8ZQ3V6Y7M2N4P6R8S0T2V6D", permit_id=permit_id),
            "other_principal": command(self.server, wrong_principal, self.device_id, CAP, PAYLOAD,
                                       command_id="01J8ZQ3V6Y7M2N4P6R8S0T2V6E", permit_id=permit_id),
        }
        for name, response in cases.items():
            with self.subTest(binding=name):
                self.assertEqual(status_of(response), "rejected", response)
                # WP-04 4d: CAP is not bound to "aux", so that command is
                # refused at plan 3.6 step 3 (MHS.CAPABILITY.NOT_BOUND), before
                # the permit is looked at; a permit used on another bound
                # resource is tests/safety/test_bindings_revisions.py.
                expected = ("MHS.CAPABILITY.NOT_BOUND" if name == "other_resource"
                            else "MHS.SAFETY.PERMIT_INVALID")
                self.assertEqual(error_code(response), expected, response)
        self.assertEqual(self._calls(), 0)

        # The rejected attempts did not consume the permit: the legal first
        # use on the bound session/device/resource/digest/principal works.
        legal = command(self.server, self.session, self.device_id, CAP, PAYLOAD,
                        command_id="01J8ZQ3V6Y7M2N4P6R8S0T2V6F", permit_id=permit_id)
        self.assertEqual(status_of(legal), "completed", legal)
        self.assertEqual(self._calls(), 1)


if __name__ == "__main__":
    unittest.main()
