"""Bounded per-grant metadata cannot alias, escape scope or outlive a grant."""
import copy
import unittest

from mhs.artifacts import ArtifactScope, LocalArtifactStore
from mhs.errors import MHSError


class ArtifactMetadataTests(unittest.TestCase):
    def make(self, **options):
        store = LocalArtifactStore(**options)
        self.addCleanup(store.close)
        store.bind("mhs://localhost/metadata")
        return store

    def publisher(self, store, command="one"):
        return store.publisher(ArtifactScope("session", "device", "main", "cap.sensing.image.v1", command), lambda: None)

    def test_metadata_and_all_descriptor_returns_are_detached_per_grant(self):
        store = self.make()
        value = {"test": {"stamp": {"secs": 1}, "tags": ["first"]}}
        expected = copy.deepcopy(value)
        pub = self.publisher(store)
        desc = pub.publish(b"pixels", "image/png", x_vendor=value)
        value["test"]["stamp"]["secs"] = 99
        desc["x-vendor"]["test"]["tags"].append("caller")
        prepared = pub.prepare({"image_ref": desc["uri"]})
        self.assertEqual(prepared[0]["x-vendor"], expected)
        prepared[0]["x-vendor"].clear()
        pub.commit()
        read = store.read(desc["uri"], "session", lambda scope: None)
        self.assertEqual(read["descriptor"]["x-vendor"], expected)
        read["descriptor"]["x-vendor"].clear()
        self.assertEqual(store.read(desc["uri"], "session", lambda scope: None)["descriptor"]["x-vendor"], expected)
        second = self.publisher(store, "two")
        different = second.publish(b"pixels", "image/png", x_vendor={"test": "different"})
        second.prepare({"image_ref": different["uri"]}); second.commit()
        self.assertEqual(different["digest"], desc["digest"])
        self.assertNotEqual(different["uri"], desc["uri"])
        self.assertEqual(store._total_bytes, 6)

    def test_structural_numeric_utf8_and_byte_limits_refuse_before_any_allocation(self):
        store = self.make()
        cyclic = {}; cyclic["self"] = cyclic
        nested = {}
        for _ in range(8): nested = {"next": nested}
        invalid = [[], {1: "not a string key"}, {"x": float("nan")}, {"x": float("inf")},
                   {"x": 2 ** 80}, {"x": object()}, {"x": b"bytes"}, cyclic, nested,
                   {str(i): None for i in range(129)}, {"x": [0] * 128},
                   {"x": "a" * 4096}, {"x": "é" * 2200}, {"x": "\ud800"}, {"x" * 129: None}]
        for value in invalid:
            with self.subTest(value=repr(value)[:80]):
                pub = self.publisher(store)
                with self.assertRaises(MHSError): pub.publish(b"pixels", "image/png", x_vendor=value)
                self.assertEqual(store._grants, {})
                self.assertEqual(store._blobs, {})
                self.assertEqual(list(store._root.iterdir()), [])
                pub.abort()

    def test_generic_artifact_ref_legacy_omission_and_abort_still_work(self):
        store = self.make()
        plain = self.publisher(store).publish(b"old", "image/png")
        self.assertNotIn("x-vendor", plain)
        pub = self.publisher(store, "generic")
        desc = pub.publish(b"data", "application/octet-stream", output_field="artifact_ref", x_vendor={"id": 1})
        pub.prepare({"artifact_ref": desc["uri"]})
        pub.commit()
        self.assertEqual(store.read(desc["uri"], "session", lambda scope: None)["descriptor"], desc)
        abandoned = self.publisher(store, "abort")
        rejected = abandoned.publish(b"partial", "image/png", x_vendor={"id": 2})
        abandoned.abort()
        with self.assertRaises(MHSError): store.read(rejected["uri"], "session", lambda scope: None)

    def test_oversized_metadata_does_not_consume_a_single_available_grant(self):
        store = self.make(max_artifacts=1)
        pub = self.publisher(store)
        with self.assertRaises(MHSError): pub.publish(b"image", "image/png", x_vendor={"x": "a" * 4096})
        desc = pub.publish(b"image", "image/png", x_vendor={"ok": True})
        pub.prepare({"image_ref": desc["uri"]}); pub.commit()
        self.assertEqual(store.read(desc["uri"], "session", lambda scope: None)["descriptor"], desc)


if __name__ == "__main__":
    unittest.main()
