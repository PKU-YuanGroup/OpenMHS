"""Acceptance run of the LumiPy package: the gate plus cases specific to this driver.

The cases use the package fake through the stock loader and server.  Nothing imports the
upstream clone or pqlumi, and no hardware is claimed.
"""

import unittest
from pathlib import Path

from mhs.adapter import load
from mhs.adapter import close_server
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
OVERLAY = str(HERE / "site-limits.example.json")
LIMITS_UNSET = "MHS.SAFETY.LIMITS_UNSET"
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class LumipyCases(unittest.TestCase):
    def serve(self, overlay=None):
        server = load(HERE, backend="fake", site_limits=overlay)
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        return client

    def state(self, client):
        return client.read("main", **self.ids)["state"]

    def configure(self, client, **patch):
        return client.invoke("cap.device.configure.v1", patch, **self.ids)

    def action(self, client, capability_id, arguments=None):
        return client.invoke(capability_id, arguments or {}, **self.ids)

    def test_the_upstream_surface_is_readable(self) -> None:
        client = self.serve()
        state = self.state(client)
        self.assertEqual(state["analysis_names"], ["placeholder_analysis"])
        self.assertFalse(state["running"])
        self.assertEqual(state["scan_range_width"], 100e-6)
        self.assertEqual(state["image_size"], [3, 3])
        self.assertEqual(state["num_frames"], 1)
        self.assertFalse(state["write_ptu_file"])
        self.assertEqual(state["path_to_ptu"], "")

    def test_the_analysis_queries_return_the_complete_fake_result(self) -> None:
        client = self.serve()
        curve = self.action(client, "x-cap.picoquant.get_analysis_curve.v1",
                            {"name": "placeholder_analysis", "curve_type": "placeholder_curve"})
        self.assertEqual(curve["status"], "completed", curve)
        self.assertEqual(curve["output"]["data_x"], [1.0, 2.0, 3.0, 4.0, 5.0])
        self.assertEqual(curve["output"]["unit_x"], "s")
        image = self.action(client, "x-cap.picoquant.get_analysis_image.v1",
                            {"name": "placeholder_analysis", "img_type": "placeholder_image"})
        self.assertNotEqual(image["status"], "completed", image)    # not served: NEEDS_ARTIFACTS (model review)
        param = self.action(client, "x-cap.picoquant.get_analysis_param.v1",
                            {"name": "placeholder_analysis", "param_type": "placeholder_param"})
        self.assertEqual(param["status"], "completed", param)
        self.assertEqual(param["output"]["param"], {"placeholder_param": 1.0})
        types = self.action(client, "x-cap.picoquant.get_analysis_curve_types.v1",
                            {"name": "placeholder_analysis"})
        self.assertEqual(types["output"], {"types": ["placeholder_curve"]})

    def test_the_example_overlay_permits_and_bounds_the_writes(self) -> None:
        client = self.serve(OVERLAY)
        receipt = self.configure(client, scan_range_width=50e-6, image_size=[32, 16])
        self.assertEqual(receipt["status"], "completed", receipt)
        stop = self.action(client, "x-cap.picoquant.configure_image_stop.v1",
                           {"stop_on_num_frames": True, "num_frames": 3,
                            "stop_on_photons_in_brightest_px": True, "photons_in_brightest_px": 500,
                            "img_stop_on_meas_time": True, "img_meas_time": 2.5})
        self.assertEqual(stop["status"], "completed", stop)
        point = self.action(client, "x-cap.picoquant.configure_point_stop.v1",
                            {"point_stop_on_photons": True, "point_num_photons": 250,
                             "point_stop_on_meas_time": True, "point_meas_time": 1.5})
        self.assertEqual(point["status"], "completed", point)
        ptu = self.action(client, "x-cap.picoquant.set_ptu_output.v1", {"write_ptu_file": True})
        self.assertEqual(ptu["status"], "completed", ptu)
        state = self.state(client)
        self.assertEqual(state["scan_range_width"], 50e-6)
        self.assertEqual(state["image_size"], [32, 16])
        self.assertEqual(state["num_frames"], 3)
        self.assertEqual(state["photons_in_brightest_px"], 500)
        self.assertEqual(state["img_meas_time"], 2.5)
        self.assertEqual(state["point_num_photons"], 250)
        self.assertEqual(state["point_meas_time"], 1.5)
        self.assertTrue(state["write_ptu_file"])
        refused = self.configure(client, scan_range_width=500e-6)
        self.assertEqual(refused["status"], "rejected", refused)
        self.assertEqual(refused["error"]["mhs_code"], ENVELOPE)
        refused = self.action(client, "x-cap.picoquant.configure_image_stop.v1",
                              {"stop_on_num_frames": True, "num_frames": 20000,
                               "stop_on_photons_in_brightest_px": False, "photons_in_brightest_px": 500,
                               "img_stop_on_meas_time": False, "img_meas_time": 2.5})
        self.assertEqual(refused["status"], "rejected", refused)
        self.assertEqual(refused["error"]["mhs_code"], ENVELOPE)

    def test_operator_required_refuses_without_an_overlay(self) -> None:
        client = self.serve()
        refused = self.configure(client, scan_range_width=50e-6)
        self.assertEqual(refused["status"], "rejected", refused)
        self.assertEqual(refused["error"]["mhs_code"], LIMITS_UNSET)
        refused = self.action(client, "x-cap.picoquant.configure_image_stop.v1",
                              {"stop_on_num_frames": True, "num_frames": 3,
                               "stop_on_photons_in_brightest_px": False, "photons_in_brightest_px": 500,
                               "img_stop_on_meas_time": False, "img_meas_time": 2.5})
        self.assertEqual(refused["status"], "rejected", refused)
        self.assertEqual(refused["error"]["mhs_code"], LIMITS_UNSET)
        self.assertEqual(self.state(client)["scan_range_width"], 100e-6)

    def test_start_stop_and_the_estop_latch(self) -> None:
        client = self.serve()
        started = self.action(client, "x-cap.picoquant.start_measurement.v1", {"meas_type": "image"})
        self.assertEqual(started["status"], "completed", started)
        self.assertTrue(started["output"]["running"])
        self.assertTrue(self.state(client)["running"])
        stopped = self.action(client, "x-cap.picoquant.stop_measurement.v1")
        self.assertEqual(stopped["status"], "completed", stopped)
        self.assertFalse(stopped["output"]["running"])
        self.action(client, "x-cap.picoquant.start_measurement.v1", {"meas_type": "point"})
        self.assertTrue(self.state(client)["running"])
        client.estop("test", **self.ids)
        self.assertFalse(self.state(client)["running"])
        refused = self.action(client, "x-cap.picoquant.start_measurement.v1", {"meas_type": "image"})
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(client.reset(self.ids["device_id"], session_id=self.ids["session_id"])["status"],
                         "completed")

    def test_a_stop_that_leaves_the_measurement_running_is_not_a_safe_state(self) -> None:
        server = load(HERE, backend="fake")
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        ids = {"device_id": device_id, "session_id": session}
        bridge = server.devices[device_id]
        native = getattr(bridge, "native", None) or getattr(getattr(bridge, "bridge", None), "native", None)
        started = client.invoke("x-cap.picoquant.start_measurement.v1", {"meas_type": "image"}, **ids)
        self.assertEqual(started["status"], "completed", started)
        native.stop_ignored = True
        refused = client.invoke("x-cap.picoquant.stop_measurement.v1", {}, **ids)
        self.assertEqual(refused["status"], "failed", refused)
        self.assertEqual(refused["error"]["mhs_code"], "MHS.SAFETY.SAFE_STATE_UNREACHED", refused)
        stopped = client.estop("test", **ids)
        self.assertEqual(stopped["status"], "failed", stopped)
        self.assertFalse(stopped["output"]["safe_state_achieved"])
        self.assertTrue(native.meas_status())


if __name__ == "__main__":
    unittest.main()
