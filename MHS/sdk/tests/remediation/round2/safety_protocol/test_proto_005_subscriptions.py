"""RE-PROTO-005: bounded subscription buffers keep ordered, accurate gaps."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from _fixtures import (  # noqa: E402
    error_code,
    make_device,
    make_server,
    open_session,
    result,
)

BUFFER = 8
PUBLICATIONS = 20


def _plain(value):
    return value.to_dict() if hasattr(value, "to_dict") else value


class SubscriptionGapTests(unittest.TestCase):
    def setUp(self) -> None:
        self.device, self.bridge = make_device("subscribe")
        self.server = make_server(self.device)
        self.device_id = self.device.device_id
        self.session = open_session(self.server, [self.device_id])
        subscribed = result(self.server.handle(
            {"jsonrpc": "2.0", "id": "sub", "method": "mhs.subscribe",
             "params": {"session_id": self.session, "device_id": self.device_id,
                        "streams": ["state"], "deadline_ms": 1000}}
        ))
        self.subscription_id = subscribed["subscription_id"]
        # The finding specifies a buffer of 8; the production default remains 256.
        self.server._subscriptions[self.subscription_id]["max_buffer"] = BUFFER

    def _publish(self, start: int, stop: int) -> None:
        for index in range(start, stop):
            self.server._notify("state", self.device_id, {"n": index})

    def _drain(self) -> list[dict]:
        return [_plain(event)["params"] for event in
                self.server.take_notifications_for(self.subscription_id)]

    def _subscribe_more(self):
        response = self.server.handle(
            {"jsonrpc": "2.0", "id": "sub", "method": "mhs.subscribe",
             "params": {"session_id": self.session, "device_id": self.device_id,
                        "streams": ["state"], "deadline_ms": 1000}}
        )
        return response.to_dict() if hasattr(response, "to_dict") else response

    def test_overflow_delivers_ordered_events_and_one_accurate_gap(self) -> None:
        self._publish(0, PUBLICATIONS)
        buffered = self.server._subscriptions[self.subscription_id]["events"]
        self.assertLessEqual(len(buffered), BUFFER, "the queue exceeded its declared bound")

        events = self._drain()
        self.assertLessEqual(len(events), BUFFER)
        sequences = [event["seq"] for event in events]
        self.assertEqual(sequences, sorted(sequences), f"sequences are not ordered: {sequences}")
        self.assertEqual(len(set(sequences)), len(sequences), "a sequence was reused")

        gaps = [event for event in events if event.get("type") == "gap"]
        self.assertEqual(len(gaps), 1, f"expected exactly one coalesced gap: {events}")
        samples = [event for event in events if event.get("type") != "gap"]
        delivered_seqs = {event["seq"] for event in samples}

        gap = gaps[0]
        self.assertEqual((gap.get("stream"), gap.get("type")), ("control", "gap"), gap)
        start, stop = gap.get("from"), gap.get("to")
        self.assertIsInstance(start, int, gap)
        self.assertIsInstance(stop, int, gap)
        expected_dropped = PUBLICATIONS - len(samples)
        self.assertEqual(stop - start + 1, expected_dropped,
                         f"gap {start}..{stop} does not describe exactly {expected_dropped} drops: {events}")
        inside = delivered_seqs.intersection(range(start, stop + 1))
        self.assertFalse(inside, f"gap {start}..{stop} includes delivered sequences {sorted(inside)}")

        delivered_n = [event["payload"]["n"] for event in samples]
        self.assertEqual(sorted(delivered_n), list(range(min(delivered_n), max(delivered_n) + 1)),
                         f"the surviving samples are not one contiguous run: {delivered_n}")
        self.assertEqual(max(delivered_n), PUBLICATIONS - 1)
        self.assertEqual(len(samples), BUFFER - 1)

        # A later publication without overflow must not re-emit the old gap.
        self._publish(PUBLICATIONS, PUBLICATIONS + 1)
        after = self._drain()
        self.assertEqual(len(after), 1, f"expected only the new sample after drain: {after}")
        self.assertNotEqual(after[0].get("type"), "gap", after)
        self.assertEqual(after[0]["payload"]["n"], PUBLICATIONS)
        self.assertGreater(after[0]["seq"], max(sequences),
                           "the new delivery sequence must advance monotonically")

    def test_subscription_limit_is_retained(self) -> None:
        active = 1  # the subscription created in setUp
        while active < 64:
            response = self._subscribe_more()
            self.assertIn("result", response, response)
            active += 1
        rejected = self._subscribe_more()
        self.assertNotIn("result", rejected, rejected)
        self.assertEqual(error_code(rejected), "MHS.LIMIT.SUBSCRIPTION_LIMIT", rejected)


if __name__ == "__main__":
    unittest.main()
