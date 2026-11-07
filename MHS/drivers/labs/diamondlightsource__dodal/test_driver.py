"""Acceptance run of the Eiger detector package: the gate, plus cases for this driver.

Add cases, never remove the check_driver call.  Since the re-authoring of 2026-11-05 (model review) the native stop()
carries the operator's DetectorParams and completes on the fake as the pinned upstream does; the cases below also keep
the upstream traps exercised: a stop() after an earlier stop or unstage does nothing, a stop() that must wait for a
running arming or an unfinished unstage fails, and the e-stop then reports SAFE_STATE_UNREACHED with the latch held.
The file action publishes the fake Odin's placeholder files through the SDK's native-file artifacts.
"""

import hashlib
import io
import json
import os
import threading
import unittest
import zipfile
from pathlib import Path

from mhs.adapter import close_server, load_driver
from mhs.artifacts import LocalArtifactStore
from mhs.driver import build_server
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
STAGE = "x-cap.diamondlightsource.eiger-stage.v1"
UNSTAGE = "x-cap.diamondlightsource.eiger-unstage.v1"
DISARM = "x-cap.diamondlightsource.eiger-disarm.v1"
FILES = "x-cap.diamondlightsource.eiger-files.v1"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
UNREACHED = "MHS.SAFETY.SAFE_STATE_UNREACHED"
UNMET = "MHS.DEVICE.PRECONDITION_UNMET"
FIELDS = ("acquisition_id", "armed", "bit_depth", "stale_params")


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class EigerDetectorCases(unittest.TestCase):
    def serve(self, *, store=True):
        driver = load_driver(HERE, backend="fake")
        artifacts = LocalArtifactStore() if store else None
        server = build_server(driver, artifact_store=artifacts)
        self.addCleanup(close_server, server)
        self.server = server
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        return client, driver.native

    def state(self, client):
        return client.read("main", **self.ids)["state"]

    def invoke(self, client, capability):
        return client.invoke(capability, {}, **self.ids)

    def test_reads_are_the_fake_placeholders(self) -> None:
        client, _fake = self.serve()
        state = self.state(client)
        self.assertEqual(sorted(state), sorted(FIELDS))
        self.assertIs(state["armed"], False)              # placeholder: the fake starts disarmed
        self.assertEqual(state["bit_depth"], 16)          # placeholder
        self.assertEqual(state["stale_params"], 0)        # placeholder
        self.assertEqual(state["acquisition_id"], "fake_1")  # placeholder prefix and run number of the fake

    def test_a_collection_stages_writes_unstages_and_publishes_its_files(self) -> None:
        client, fake = self.serve()
        staged = self.invoke(client, STAGE)
        self.assertEqual(staged["status"], "completed", staged)
        self.assertEqual(staged["output"], {"armed": True, "armed_here": True})
        again = self.invoke(client, STAGE)                # upstream stage() does nothing on an armed detector
        self.assertEqual(again["output"], {"armed": True, "armed_here": False})
        self.assertEqual(fake.odin.file_writer.file_path.get(), fake.detector_params.directory)
        self.assertEqual(fake.odin.file_writer.capture.get(), 1)
        # While the detector is armed and Odin writes, the file action refuses.
        writing = self.invoke(client, FILES)
        self.assertEqual(writing["status"], "failed", writing)
        self.assertEqual(writing["error"]["mhs_code"], UNMET)
        self.assertNotIn("artifacts", writing)
        ended = self.invoke(client, UNSTAGE)
        self.assertEqual(ended["status"], "completed", ended)
        self.assertEqual(ended["output"], {"armed": False, "staged": True, "odin_ok": True})
        self.assertTrue(fake.disarming_status.done)
        self.assertEqual(fake.collections, 2)             # placeholder: the starting collection and this one
        published = self.invoke(client, FILES)
        self.assertEqual(published["status"], "completed", published)
        self.assertEqual(published["output"]["acquisition_id"], "fake_1")
        self.assertEqual(published["output"]["files"], 2)
        descriptor = published["artifacts"][0]
        self.assertEqual(descriptor["uri"], published["output"]["artifact_ref"])
        self.assertEqual(descriptor["media_type"], "application/zip")
        listed = descriptor["x-vendor"]["openmhs.native_files"]
        self.assertEqual(listed["cleanup"], "keep")
        directory = fake.detector_params.directory
        names = sorted(os.listdir(directory))
        self.assertEqual(names, ["fake_1_000001.h5", "fake_1_meta.h5"])
        on_disk = {name: Path(directory, name).read_bytes() for name in names}
        self.assertEqual([item["name"] for item in listed["files"]], names)
        for item in listed["files"]:
            self.assertEqual(item["sha256"], hashlib.sha256(on_disk[item["name"]]).hexdigest())
            self.assertEqual(item["media_type"], "application/x-hdf5")
        data = self.server.read_artifact(descriptor["uri"], session_id=self.ids["session_id"])["data"]
        self.assertEqual(descriptor["digest"], "sha256:" + hashlib.sha256(data).hexdigest())
        archive = zipfile.ZipFile(io.BytesIO(data))
        self.assertEqual(archive.namelist(), ["manifest.json"] + [f"files/{name}" for name in names])
        for name in names:
            self.assertEqual(archive.read(f"files/{name}"), on_disk[name])
        self.assertEqual(json.loads(archive.read("manifest.json"))["format"], "openmhs.native-files.v1")
        # cleanup "keep": the published files are still where Odin wrote them
        self.assertEqual({name: Path(directory, name).read_bytes() for name in names}, on_disk)

    def test_a_detector_armed_elsewhere_is_not_unstaged_by_this_connection(self) -> None:
        client, fake = self.serve()
        fake.odin.fan.ready.set(1)                        # placeholder: armed by another client
        fake.cam.acquire.set(1)                           # placeholder
        staged = self.invoke(client, STAGE)
        self.assertEqual(staged["output"], {"armed": True, "armed_here": False})
        ended = self.invoke(client, UNSTAGE)
        self.assertEqual(ended["status"], "completed", ended)
        self.assertEqual(ended["output"], {"armed": False, "staged": False, "odin_ok": False})
        self.assertIsNone(fake.disarming_status)          # upstream unstage, which would raise here, was not called

    def test_unstage_without_a_staged_collection_only_clears_the_acquire(self) -> None:
        client, fake = self.serve()
        fake.cam.acquire.set(1)                           # placeholder: the camera acquire switched on elsewhere
        receipt = self.invoke(client, UNSTAGE)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(receipt["output"], {"armed": False, "staged": False, "odin_ok": False})
        self.assertEqual(fake.cam.acquire.get(), 0)
        self.assertIsNone(fake.disarming_status)          # upstream unstage was not called
        stopped = client.estop("test", **self.ids)
        self.assertEqual(stopped["status"], "completed", stopped)
        self.assertEqual(fake.stop_cleanups, 1)           # the native stop still ran its cleanup

    def test_the_disarm_action_is_the_safe_state(self) -> None:
        client, fake = self.serve()
        fake.cam.acquire.set(1)                           # placeholder
        receipt = self.invoke(client, DISARM)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(receipt["output"], {"armed": False})
        self.assertEqual(fake.cam.acquire.get(), 0)

    def test_the_estop_runs_the_native_cleanup_with_detector_params(self) -> None:
        client, fake = self.serve()
        self.assertEqual(self.invoke(client, STAGE)["status"], "completed")
        stopped = client.estop("test", **self.ids)
        self.assertEqual(stopped["status"], "completed", stopped)
        self.assertIs(stopped["output"]["safe_state_achieved"], True)
        self.assertEqual(fake.stop_cleanups, 1)
        self.assertTrue(fake.disarming_status.done)
        self.assertEqual(fake.cam.acquire.get(), 0)
        self.assertEqual(fake.odin.file_writer.capture.get(), 0)
        self.assertEqual(fake.odin.meta.stop_writing.get(), 1)
        self.assertEqual(fake.cam.roi_mode.get(), 0)
        full = fake.detector_params.detector_size_constants.det_size_pixels
        self.assertEqual((fake.odin.file_writer.image_width.get(), fake.odin.file_writer.image_height.get()),
                         (full.width, full.height))
        self.assertEqual(fake.odin.fan.dev_shm_enable.get(), 0)
        calls = fake.stop_calls
        refused = self.invoke(client, STAGE)
        self.assertEqual(refused["status"], "rejected", refused)
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(fake.stop_calls, calls)
        self.assertFalse(fake.is_armed())

    def test_a_later_native_stop_does_nothing_but_the_disarm_action_clears_the_acquire(self) -> None:
        # eiger.py:212-213: once a stop or unstage finished disarming_status, stop() only logs "Already disarmed".
        client, fake = self.serve()
        self.assertEqual(client.estop("first", **self.ids)["status"], "completed")
        reset = client.reset(**self.ids)
        self.assertEqual(reset["status"], "completed", reset)
        fake.cam.acquire.set(1)                           # placeholder: the camera acquire switched on elsewhere
        second = client.estop("second", **self.ids)
        self.assertEqual(second["status"], "completed", second)
        self.assertEqual(fake.stop_cleanups, 1)           # the second native stop() ran no cleanup
        self.assertEqual(fake.cam.acquire.get(), 0)       # the safe-state action did

    def test_a_stop_that_waits_for_a_running_arming_reports_unreached(self) -> None:
        client, fake = self.serve()
        fake.arming_status.done = False                   # placeholder: an arming chain still running
        stopped = client.estop("test", **self.ids)
        self.assertEqual(stopped["status"], "failed", stopped)
        self.assertEqual(stopped["error"]["mhs_code"], UNREACHED, stopped)
        self.assertIs(stopped["output"]["latched"], True)
        refused = self.invoke(client, STAGE)
        self.assertEqual(refused["status"], "rejected", refused)
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)

    def test_a_stop_is_not_confirmed_while_an_arming_chain_still_runs(self) -> None:
        # After a stop whose arming wait timed out, every later stop() is a no-op (eiger.py:210-213), but the arming
        # chain ends with set_cam_acquire (eiger.py:462): the e-stop stays unconfirmed until that chain finished.
        client, fake = self.serve()
        fake.disarming_status = type(fake.arming_status)(done=True)  # placeholder: an earlier stop finished
        fake.arming_status = type(fake.arming_status)(done=False)    # placeholder: a chain still running
        stopped = client.estop("test", **self.ids)
        self.assertEqual(stopped["status"], "failed", stopped)
        self.assertEqual(stopped["error"]["mhs_code"], UNREACHED, stopped)
        self.assertEqual(fake.stop_cleanups, 0)
        fake.arming_status.done = True                               # the chain finished
        again = client.estop("again", **self.ids)
        self.assertEqual(again["status"], "completed", again)
        self.assertIs(again["output"]["safe_state_achieved"], True)
        self.assertEqual(fake.cam.acquire.get(), 0)

    def test_an_unstage_that_raised_leaves_every_later_stop_unreached(self) -> None:
        # eiger.py:161-184: an exception skips disarming_status.set_finished(); stop() then only waits for it.
        client, fake = self.serve()
        self.assertEqual(self.invoke(client, STAGE)["status"], "completed")
        fake._writers_finish = lambda: None               # placeholder: the Odin writers never finish
        ended = self.invoke(client, UNSTAGE)
        self.assertEqual(ended["status"], "failed", ended)
        self.assertEqual(fake.cam.acquire.get(), 0)       # the finally block disarmed
        self.assertFalse(fake.disarming_status.done)
        stopped = client.estop("test", **self.ids)
        self.assertEqual(stopped["status"], "failed", stopped)
        self.assertEqual(stopped["error"]["mhs_code"], UNREACHED, stopped)
        self.assertEqual(fake.stop_cleanups, 0)

    def test_the_file_action_needs_an_artifact_store_and_the_acquisitions_files(self) -> None:
        client, fake = self.serve(store=False)
        receipt = self.invoke(client, FILES)
        self.assertEqual(receipt["status"], "failed", receipt)
        self.assertEqual(receipt["error"]["mhs_code"], "MHS.DEVICE.NOT_READY")
        client, fake = self.serve()
        directory = fake.detector_params.directory
        for name in os.listdir(directory):
            os.remove(os.path.join(directory, name))      # the fake's own temporary files
        Path(directory, "fake_10_000001.h5").write_bytes(b"other run")  # placeholder: another acquisition
        Path(directory, "fake_1.nxs").write_bytes(b"master")            # placeholder: not an Odin .h5 file
        missing = self.invoke(client, FILES)
        self.assertEqual(missing["status"], "failed", missing)
        self.assertEqual(missing["error"]["mhs_code"], UNMET)
        for index in range(9):
            Path(directory, f"fake_1_{index:06d}.h5").write_bytes(b"x")  # placeholder: too many files
        too_many = self.invoke(client, FILES)
        self.assertEqual(too_many["status"], "failed", too_many)
        self.assertEqual(too_many["error"]["mhs_code"], "MHS.CAPABILITY.OUTPUT_INVALID")
        self.assertNotIn("artifacts", too_many)

    def test_a_directory_every_user_may_write_refuses_only_the_file_action(self) -> None:
        loaded = load_driver(HERE, backend="fake")
        self.addCleanup(loaded.close)
        fake = type(loaded.native)()
        os.chmod(fake.detector_params.directory, 0o777)   # the fake's own temporary directory
        driver = type(loaded)(backend="fake", native=fake, base_dir=HERE)
        driver.setup()
        server = build_server(driver, artifact_store=LocalArtifactStore())
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        self.ids = {"device_id": device_id,
                    "session_id": client.open_session(device_ids=[device_id])["session_id"]}
        refused = self.invoke(client, FILES)
        self.assertEqual(refused["status"], "failed", refused)
        self.assertEqual(refused["error"]["mhs_code"], "MHS.DEVICE.NOT_READY")
        self.assertIn("every user", refused["error"]["message"])
        stopped = client.estop("test", **self.ids)
        self.assertEqual(stopped["status"], "completed", stopped)
        self.assertEqual(fake.stop_cleanups, 1)

    def test_the_file_action_waits_until_the_collection_ended(self) -> None:
        # integrator v4 (2026-11-05): refused while an arming chain runs, while the detector is armed (is_armed,
        # eiger.py:134-135) even when no writer reports Writing_RBV 1 yet, and while a writer still writes.
        client, fake = self.serve()
        fake.arming_status = type(fake.arming_status)(done=False)   # placeholder: an arming chain still running
        arming = self.invoke(client, FILES)
        self.assertEqual(arming["status"], "failed", arming)
        self.assertEqual(arming["error"]["mhs_code"], UNMET)
        self.assertIn("arming or armed", arming["error"]["message"])
        fake.arming_status.done = True
        fake.odin.fan.ready.set(1)                        # placeholder: armed, capture not started
        fake.cam.acquire.set(1)                           # placeholder
        self.assertEqual(fake.odin.meta.ready.get(), 0)
        armed = self.invoke(client, FILES)
        self.assertEqual(armed["status"], "failed", armed)
        self.assertEqual(armed["error"]["mhs_code"], UNMET)
        self.assertIn("arming or armed", armed["error"]["message"])
        fake.cam.acquire.set(0)                           # disarmed
        fake.odin.nodes.nodes[-1].writing.set(1)          # placeholder: one writer still writing
        writing = self.invoke(client, FILES)
        self.assertEqual(writing["status"], "failed", writing)
        self.assertEqual(writing["error"]["mhs_code"], UNMET)
        self.assertIn("still writing", writing["error"]["message"])
        fake.odin.nodes.nodes[-1].writing.set(0)
        published = self.invoke(client, FILES)
        self.assertEqual(published["status"], "completed", published)
        self.assertEqual(published["output"]["acquisition_id"], "fake_1")

    def test_a_disarm_that_outlasts_the_budget_reports_unreached(self) -> None:
        # disarm_detector waits up to the general status timeout (eiger.py:425-426; 20 s on i03): a safe-state disarm
        # still waiting after the 1 s e-stop budget reports SAFE_STATE_UNREACHED with the latch held.
        client, fake = self.serve()
        fake.disarming_status = type(fake.arming_status)(done=True)  # placeholder: an earlier stop finished
        release = threading.Event()
        quick = fake.disarm_detector

        def slow_disarm():
            release.wait(10)                              # placeholder: the acquire status not yet reported
            quick()

        fake.disarm_detector = slow_disarm
        self.addCleanup(release.set)                      # runs before the server closes
        fake.cam.acquire.set(1)                           # placeholder
        stopped = client.estop("test", **self.ids)
        self.assertEqual(stopped["status"], "failed", stopped)
        self.assertEqual(stopped["error"]["mhs_code"], UNREACHED, stopped)
        self.assertIs(stopped["output"]["latched"], True)
        refused = self.invoke(client, STAGE)
        self.assertEqual(refused["status"], "rejected", refused)
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        release.set()

    def test_an_acquisition_id_that_is_not_a_file_name_prefix_is_refused(self) -> None:
        client, fake = self.serve()
        for value in ("", "../escape", "a/b", ".hidden", "fake_1/.."):
            fake.odin.file_writer.id.set(value)           # placeholder readback values
            receipt = self.invoke(client, FILES)
            self.assertEqual(receipt["status"], "failed", receipt)
            self.assertEqual(receipt["error"]["mhs_code"], UNMET)
            self.assertIn("acquisition id", receipt["error"]["message"])

    def test_the_estop_ends_the_collection_this_connection_staged(self) -> None:
        client, fake = self.serve()
        self.assertEqual(self.invoke(client, STAGE)["status"], "completed")
        self.assertEqual(client.estop("test", **self.ids)["status"], "completed")
        self.assertEqual(client.reset(**self.ids)["status"], "completed")
        finished = fake.disarming_status
        ended = self.invoke(client, UNSTAGE)
        self.assertEqual(ended["status"], "completed", ended)
        self.assertEqual(ended["output"], {"armed": False, "staged": False, "odin_ok": False})
        self.assertIs(fake.disarming_status, finished)    # the stop's finished disarm; upstream unstage not run


if __name__ == "__main__":
    unittest.main()
