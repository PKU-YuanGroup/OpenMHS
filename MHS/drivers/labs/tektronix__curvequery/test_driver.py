"""Acceptance run of the curvequery package: the gate, plus cases for the one served action.

Add cases, never remove the check_driver call.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
CURVE_DOWNLOAD = "x-cap.tektronix.curve_download.v1"


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class WaveformDownload(unittest.TestCase):
    """The extension action on a fresh fake endpoint; the source names and sample values are test data."""

    def serve(self):
        server = load(HERE, backend="fake")
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        self.ids = {"device_id": device_id,
                    "session_id": client.open_session(device_ids=[device_id])["session_id"]}
        return client

    def test_decomposed_download_returns_traces_and_scales(self) -> None:
        client = self.serve()
        receipt = client.invoke(CURVE_DOWNLOAD, {}, **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        output = receipt["output"]
        self.assertEqual(output["sources"], ["CH1", "CH2_D0"])
        self.assertEqual(output["x_unit"], ["s", "s"])
        self.assertEqual(len(output["traces"]), 2)
        self.assertEqual(len(output["x_slope"]), 2)
        self.assertEqual(len(output["x_offset"]), 2)
        self.assertEqual(len(output["y_top"]), 2)
        self.assertEqual(len(output["y_bottom"]), 2)
        self.assertEqual(len(output["traces"][0]), len(output["traces"][1]))
        self.assertIsNotNone(output["y_top"][0])
        self.assertIsNotNone(output["y_bottom"][0])
        self.assertIsNone(output["y_top"][1])
        self.assertIsNone(output["y_bottom"][1])

    def test_undecomposed_digital_channel_returns_one_word_trace(self) -> None:
        client = self.serve()
        receipt = client.invoke(CURVE_DOWNLOAD, {"decompose_digital_channels": False}, **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        output = receipt["output"]
        self.assertEqual(output["sources"], ["CH1", "CH2"])
        self.assertIsNone(output["y_top"][1])
        self.assertIsNone(output["y_bottom"][1])

    def test_the_analog_trace_is_a_copy_of_the_feature_data(self) -> None:
        client = self.serve()
        receipt = client.invoke(CURVE_DOWNLOAD, {}, **self.ids)
        output = receipt["output"]
        self.assertEqual(output["traces"][0], [0.0, 0.5, 1.0, 0.5, 0.0, -0.5])  # placeholder test data
        self.assertEqual(output["traces"][1], [0, 1, 1, 0, 1, 0])  # placeholder test data


if __name__ == "__main__":
    unittest.main()
