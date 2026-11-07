"""Live-simulation declarations through the actual package loader and strict server."""

from __future__ import annotations

import json
import unittest
from unittest.mock import Mock, patch

from mhs.adapter import LoadError, load, load_driver
from mhs.bridge.ros_transport import WebSocketTransport
from mhs.driver import build_manifest, close_server
from mhs.driver.package import export_adapter
from mhs.errors import MHSError

from tests.driver import support
from tests.driver.test_ros_simulation import DEPLOYED_FIDELITY, Peer, deployment


def package(test):
    return support.write_package(support.temp_dir(test) / "world", {
        "driver.py": "from tests.driver.test_ros_simulation import SimWorld as _SimWorld\n"
                     "class World(_SimWorld):\n    pass\n",
    })


class RosSimulationAdapterTests(unittest.TestCase):
    def test_package_load_driver_uses_deployment_and_guards_projected_manifests(self):
        with patch("mhs.bridge.ros_transport.WebSocketTransport._connect") as connect:
            driver = load_driver(package(self), "sim", simulation_deployment=deployment())
            self.addCleanup(driver.close)
            self.assertEqual(driver.options, {})
            self.assertEqual(driver.inner.config["endpoint"], deployment()["endpoint"])
            self.assertEqual(build_manifest(driver)["fidelity"], DEPLOYED_FIDELITY)
            for backend in ("fake", "hardware"):
                with self.subTest(backend=backend), self.assertRaisesRegex(ValueError, "projected"):
                    build_manifest(driver, backend=backend)
            connect.assert_not_called()

    def test_load_runs_sdk_transport_through_stock_server_and_exports_deployed_identity(self):
        server = load(package(self), backend="sim", simulation_deployment=deployment())
        self.addCleanup(close_server, server)
        client = support.Client(server)
        peer = Peer()
        connector = Mock(return_value=peer)
        with patch("mhs.bridge.ros_transport.importlib.import_module",
                   return_value=Mock(create_connection=connector)):
            receipt = client.command("x-cap.test.state.v1")
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(receipt["output"], {"paused": True})
        self.assertTrue(receipt["device_id"].endswith("/sim/test-world"))
        self.assertEqual(next(iter(server.devices.values())).fidelity, DEPLOYED_FIDELITY)
        connector.assert_called_once()
        self.assertEqual(connector.call_args.args, (deployment()["endpoint"],))

    def test_single_driver_adapter_forwards_deployment_and_native_transport(self):
        directory = package(self)
        target = directory / "mhs-adapter.json"
        target.write_text(json.dumps(export_adapter(directory, out=target)), encoding="utf-8")
        peer = Peer()
        connector = Mock(return_value=peer)
        native = WebSocketTransport(deployment()["endpoint"], connector=connector)
        server = load(target, "sim", simulation_deployment=deployment(), native=native)
        self.addCleanup(close_server, server)
        receipt = support.Client(server).command("x-cap.test.state.v1")
        self.assertEqual(receipt["status"], "completed", receipt)
        connector.assert_called_once()

    def test_invalid_or_missing_deployment_is_refused_without_connection(self):
        directory = package(self)
        with patch("mhs.bridge.ros_transport.WebSocketTransport._connect") as connect:
            with self.assertRaisesRegex(ValueError, "exactly"):
                load(directory, "sim", simulation_deployment={"endpoint": deployment()["endpoint"]})
            with self.assertRaises(MHSError):
                load(directory, "sim")
            with self.assertRaisesRegex(ValueError, "backend='sim'"):
                load(directory, "fake", simulation_deployment=deployment())
            connect.assert_not_called()

    def test_non_ros_driver_rejects_deployment_before_factory(self):
        directory = support.write_package(support.temp_dir(self) / "other", {
            "driver.py": "from tests.driver.support import Bath as _Bath\n"
                         "class Bath(_Bath):\n    pass\n",
        })
        with patch("tests.driver.support.connect_bath") as factory:
            for loader in (load, load_driver):
                with self.subTest(loader=loader), self.assertRaises(LoadError) as caught:
                    loader(directory, "sim", simulation_deployment=deployment())
                self.assertEqual(caught.exception.reason, "simulation_deployment_invalid")
            factory.assert_not_called()

    def test_raw_bridge_adapter_rejects_deployment_before_bridge_creation(self):
        directory = package(self)
        target = directory / "mhs-adapter.json"
        document = export_adapter(directory, out=target)
        document["bridges"][0].update(kind="gymnasium", config={"env_id": "Synthetic-v0"})
        target.write_text(json.dumps(document), encoding="utf-8")
        with patch("mhs.adapter._make_bridge") as factory:
            with self.assertRaises(LoadError) as caught:
                load(target, "sim", simulation_deployment=deployment())
            self.assertEqual(caught.exception.reason, "simulation_deployment_invalid")
            factory.assert_not_called()


if __name__ == "__main__":
    unittest.main()
