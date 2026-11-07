"""Schema identity, references and agreement with live SDK output."""

from __future__ import annotations

import json
import unittest

from mhs._ids import LEGACY_SCHEMA_PREFIX, SCHEMA_BASE
from mhs.bridge.base import Bridge
from mhs.client import MHSClient
from mhs.reference import build_endpoint, build_server
from mhs.schema import SchemaStore
from mhs.server import Capability, Device, MHSServer, Resource, SafetyEnvelope, action_digest

from ._support import EXAMPLES, SCHEMA_DIR, load_json

STORE = SchemaStore(root=SCHEMA_DIR)
SCHEMAS = sorted(SCHEMA_DIR.glob("*.json"))
NEW_SCHEMAS = ("reference", "site-limits", "driver-lock", "driver-result", "check-report", "endpoints", "errors")


class _ValveBridge(Bridge):
    """Minimal bridge for the permit round trip (the permit never reaches it)."""

    bridge_id = "tests.catalog_data.valve"

    def read(self, resource_id, fields=None, ctx=None):
        return {"state": "closed"}

    def call(self, capability_id, args=None, ctx=None):
        return {"output": {"position": 100, "state": "open"}}


class _Loopback:
    """In-process transport: hand each request straight to the server."""

    def __init__(self, server):
        self.server = server

    def request(self, message, timeout=None):
        response = self.server.handle(message)
        return response.to_dict() if hasattr(response, "to_dict") else response

    def close(self):
        pass


def _refs(node):
    if isinstance(node, dict):
        for key, value in node.items():
            if key == "$ref" and isinstance(value, str):
                yield value
            else:
                yield from _refs(value)
    elif isinstance(node, list):
        for item in node:
            yield from _refs(item)


class SchemaIdentityTests(unittest.TestCase):
    def test_every_id_is_schema_base_plus_file_name(self):
        self.assertGreaterEqual(len(SCHEMAS), 20)
        for path in SCHEMAS:
            with self.subTest(schema=path.name):
                self.assertEqual(load_json(path)["$id"], SCHEMA_BASE + path.name)

    def test_new_schemas_exist(self):
        names = {path.name for path in SCHEMAS}
        for stem in NEW_SCHEMAS:
            self.assertIn(f"{stem}.schema.json", names)

    def test_no_legacy_domain_in_schemas_or_examples(self):
        legacy_host = LEGACY_SCHEMA_PREFIX.split("/")[2]
        for path in SCHEMAS + sorted(EXAMPLES.rglob("*.json")):
            with self.subTest(file=path.name):
                self.assertNotIn(legacy_host, path.read_text(encoding="utf-8"))

    def test_every_ref_is_relative_and_resolves(self):
        for path in SCHEMAS:
            document = load_json(path)
            for ref in _refs(document):
                with self.subTest(schema=path.name, ref=ref):
                    self.assertFalse(ref.startswith(("http:", "https:")), "use relative $ref")
                    target, _, fragment = ref.partition("#")
                    root = load_json(SCHEMA_DIR / target) if target else document
                    node = root
                    for token in [t for t in fragment.split("/") if t]:
                        node = node[token.replace("~1", "/").replace("~0", "~")]
                    self.assertIsInstance(node, dict)

    def test_legacy_schema_prefix_still_resolves(self):
        document, _ = STORE.load(LEGACY_SCHEMA_PREFIX + "device.schema.json")
        self.assertEqual(document["$id"], SCHEMA_BASE + "device.schema.json")


class TypedLimitTests(unittest.TestCase):
    """The closed limit rule rejects typos that used to remove a bound silently."""

    def _device(self, rule):
        return {
            "mhs_version": "1.0", "device_id": "mhs://localhost/t/x", "instance_id": "01JB2C3D4E5F6G7H8J9KAMBNCP",
            "display_name": "x", "mode": "hardware",
            "resources": [{"resource_id": "r", "kind": "thermal.zone", "state_schema": {"type": "object"}}],
            "capabilities": [{"capability_id": "cap.thermal.setpoint.v1", "resource": "r",
                              "limits": {"target_temperature": rule}}],
            "safety": {"risk_class": "R2", "estop": {"kind": "hardware", "latching": True},
                       "safe_state": {"description": "off", "achieved_by": []}},
        }

    def test_rule_members(self):
        self.assertEqual(STORE.validate(self._device({"min": 0, "max": 90, "unit": "Cel"}), "device.schema.json"), [])
        self.assertEqual(STORE.validate(self._device("operator_required"), "device.schema.json"), [])
        self.assertTrue(STORE.validate(self._device({"maxx": 90}), "device.schema.json"))
        self.assertTrue(STORE.validate(self._device("operator-required"), "device.schema.json"))
        self.assertTrue(STORE.validate(self._device({}), "device.schema.json"))
        self.assertTrue(STORE.validate(self._device({"max": "90"}), "device.schema.json"))
        self.assertTrue(STORE.validate(self._device({"max": 90, "source": "upstream_code"}), "device.schema.json"),
                        "upstream_code needs a file:line ref")
        self.assertEqual(STORE.validate(self._device({"max": [1, 2], "names": ["a", "b"]}), "device.schema.json"), [])

    def test_cumulative_window_rules_stay_valid(self):
        # SAFE-004 fixtures declare {max, per}; the closed rule keeps that member.
        self.assertEqual(STORE.validate(self._device({"min": 0, "max": 10, "per": "rolling_24h", "unit": "1"}),
                                        "device.schema.json"), [])


class LiveOutputTests(unittest.TestCase):
    def test_reference_endpoint_manifests_validate(self):
        for name in ("conveyor", "lab", "arm"):
            spec = build_endpoint(name, test_profile=True)
            try:
                client = MHSClient(_Loopback(build_server(spec, log_ready=False)))
                client.hello()
                for manifest in client.devices():
                    with self.subTest(endpoint=name, device=manifest["device_id"]):
                        self.assertEqual(STORE.validate(manifest, "device.schema.json"), [])
            finally:
                spec.close()

    def test_live_permit_validates_against_permit_schema(self):
        # SC-08: the published permit schema rejected the live mhs.safety.permit result.
        device = Device(
            "mhs://localhost/tests/permit",
            mode="simulated",
            resources=[Resource("valve", "actuation.valve", state_schema={"type": "object"}, state={})],
            capabilities=[Capability("cap.actuation.valve.v1", "valve",
                                     input_schema={"type": "object", "properties": {"state": {"enum": ["open", "closed"]}}},
                                     requires_permit=True)],
            safety=SafetyEnvelope(risk_class="R1"),
            fidelity={"engine": "test", "fidelity_level": "F0", "determinism": {"kind": "exact"}},
            bridge=_ValveBridge(device_id="mhs://localhost/tests/permit"),
        )
        server = MHSServer("mhs://localhost:7400", [device], log_ready=False)
        client = MHSClient(_Loopback(server))
        client.hello()
        session = client.open_session([device.device_id], mode="simulated")["session_id"]
        payload = {"state": "open"}
        permit = client.request("mhs.safety.permit", {
            "session_id": session, "device_id": device.device_id, "capability_id": "cap.actuation.valve.v1",
            "input_digest": action_digest("cap.actuation.valve.v1", "valve", payload), "input": payload,
        })
        self.assertEqual(STORE.validate(permit, "permit.schema.json"), [], json.dumps(permit)[:400])
        self.assertEqual(permit["scope"]["device_id"], device.device_id)


if __name__ == "__main__":
    unittest.main()
