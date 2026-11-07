"""Fake backend of the Eiger detector package: a source-shaped stand-in for dodal's classic ``EigerDetector``.

It reproduces, for the paths this package touches, the pinned upstream at f96fef4e (``src/dodal/devices/eiger.py``,
``src/dodal/devices/eiger_odin.py``):

* ``stage`` (eiger.py:142-147) waits on a started arming and, when the detector is not armed, runs ``async_stage``
  (:122-132: ``disarming_status`` reset to None, Odin errors cleared, Odin initialised) and waits for the arming chain
  (:436-469).  The fake's chain applies the parts that change what the package reads: Odin's file path and file name
  from the ``DetectorParams`` (``set_odin_pvs``, :286-306, so ``AcquisitionID_RBV`` becomes ``full_filename``), the
  writers start (``capture`` 1 and ``Writing_RBV`` 1, ``_wait_for_odin_status`` :389-402), the camera acquire (:432-434),
  ``filewriters_finished`` from Odin (:404-407) and the fan ready.
* ``unstage`` (:161-184) and ``stop`` (:186-213) follow the upstream statement by statement, including the
  ``disarming_status`` logic: ``stop`` cleans up only when no disarm ran since the last arming (otherwise it waits for an
  unfinished one, or logs "Already disarmed, doing nothing"), and an ``unstage`` without a prior arming raises
  ``AttributeError`` on ``filewriters_finished`` after its ``finally`` block disarmed, leaving ``disarming_status``
  unfinished.  ``disable_roi_mode`` sets ``roi_mode`` 0 and the full detector size of the ``DetectorParams``
  (:215-249).
* Odin (eiger_odin.py): ``stop`` sets ``capture`` 0 and ``meta.stop_writing`` 1 (:169-174); the writers then finish;
  ``create_finished_status`` is done when ``meta.ready`` (Writing_RBV) and every node's ``writing`` are 0 (:125-129).

What a real Odin does between arming and the end of writing (frames on external triggers, HDF5 data and meta files)
is not modelled: when the fake's writers finish, they write two placeholder files, ``<acquisition id>_000001.h5`` and
``<acquisition id>_meta.h5``, into the fake's own private temporary directory (``DetectorParams.directory``).  The
clone does not state the names Odin gives its files; these names, their bytes and every number below are
placeholders.  The fake starts disarmed with the files of one finished earlier collection of its acquisition id on
disk, so the package's file action has something to publish on a fresh fake.  ``Status.wait`` of an unfinished
status raises at once (the upstream waits for its timeout, then raises); the fake never sleeps.  The fake removes its
temporary directory when it is garbage-collected; the gate's child processes end with ``os._exit``, so a fake that
uncollected SDK objects still reference at that point leaves its small directory behind (``openmhs-dodal-fake-*``,
two placeholder files) for the system's temporary-file cleanup.  No ophyd, dodal, EPICS, Odin or network code is
imported or run.
"""

import os
import shutil
import tempfile
import weakref


class _FakeStatus:
    """An ophyd-like status: ``wait`` returns when done and raises when not (the upstream would time out first)."""

    def __init__(self, done=True):
        self.done = done

    def set_finished(self):
        self.done = True

    def wait(self, timeout=None):
        if not self.done:
            raise TimeoutError("status not finished within its timeout")
        return self

    def __and__(self, other):
        return _FakeStatus(self.done and other.done)


class _FakeSignal:
    """One Signal: ``get`` returns the stored value; ``set`` stores it and returns a finished status."""

    def __init__(self, value):
        self._value = value

    def get(self):
        return self._value

    def set(self, value, timeout=None, **_kwargs):
        self._value = value
        return _FakeStatus()


class _FakeCam:
    def __init__(self):
        self.acquire = _FakeSignal(0)   # placeholder: the fake starts with the camera acquire off
        self.roi_mode = _FakeSignal(0)  # placeholder


class _FakeFan:
    def __init__(self):
        self.ready = _FakeSignal(0)           # placeholder: StateReady_RBV
        self.dev_shm_enable = _FakeSignal(0)  # placeholder: DevShmCache


class _FakeMeta:
    def __init__(self):
        self.ready = _FakeSignal(0)        # Writing_RBV of the meta listener (eiger_odin.py:29)
        self.file_name = _FakeSignal("")   # placeholder
        self.stop_writing = _FakeSignal(0)


class _FakeFileWriter:
    def __init__(self):
        self.id = _FakeSignal("")             # AcquisitionID_RBV (eiger_odin.py:39)
        self.file_path = _FakeSignal("")      # placeholder
        self.file_name = _FakeSignal("")      # placeholder
        self.capture = _FakeSignal(0)
        self.start_timeout = _FakeSignal(0)
        self.image_height = _FakeSignal(0)    # placeholder
        self.image_width = _FakeSignal(0)     # placeholder
        self.num_row_chunks = _FakeSignal(0)  # placeholder
        self.num_col_chunks = _FakeSignal(0)  # placeholder


class _FakeNode:
    def __init__(self):
        self.writing = _FakeSignal(0)           # Writing_RBV of one file-writer node (eiger_odin.py:46)
        self.frames_dropped = _FakeSignal(0)    # placeholder
        self.frames_timed_out = _FakeSignal(0)  # placeholder


class _FakeNodes:
    def __init__(self):
        self.node_0, self.node_1, self.node_2, self.node_3 = _FakeNode(), _FakeNode(), _FakeNode(), _FakeNode()

    @property
    def nodes(self):
        return [self.node_0, self.node_1, self.node_2, self.node_3]

    def clear_odin_errors(self):
        return None


class _FakeFinished:
    """``create_finished_status``: done once the meta listener and every node stopped writing (eiger_odin.py:125-129)."""

    def __init__(self, odin):
        self._odin = odin

    @property
    def done(self):
        return self._odin.writing_finished()

    def wait(self, timeout=None):
        if not self.done:
            raise TimeoutError("Odin writers still writing")
        return self


class _FakeOdin:
    def __init__(self, detector):
        # A weak reference: no cycle keeps the fake alive, so its directory goes when its endpoint drops it (the
        # gate's child processes end with os._exit, which runs no exit-time cleanup).
        self._detector = weakref.ref(detector)
        self.fan = _FakeFan()
        self.file_writer = _FakeFileWriter()
        self.meta = _FakeMeta()
        self.nodes = _FakeNodes()

    def writing_finished(self):
        return self.meta.ready.get() == 0 and all(node.writing.get() == 0 for node in self.nodes.nodes)

    def create_finished_status(self):
        return _FakeFinished(self)

    def wait_for_odin_initialised(self, timeout):
        return True, ""

    def check_and_wait_for_odin_state(self, timeout):
        return True

    def stop(self):
        status = self.file_writer.capture.set(0)
        status &= self.meta.stop_writing.set(1)
        detector = self._detector()
        if detector is not None:
            detector._writers_finish()
        return status


class _FakeSize:
    def __init__(self, width, height):
        self.width = width
        self.height = height


class _FakeSizeConstants:
    def __init__(self):
        self.det_size_pixels = _FakeSize(4148, 4362)  # placeholder (the upstream default is EIGER2_X_16M_SIZE)
        self.roi_size_pixels = _FakeSize(2068, 2162)  # placeholder


class _FakeDetectorParams:
    """The parts of ``DetectorParams`` the fake reads; every value is a placeholder, not a deployment's."""

    def __init__(self, directory):
        self.directory = directory + "/"      # the upstream validator returns the path with a trailing slash
        self.prefix = "fake"                  # placeholder
        self.run_number = 1                   # placeholder
        self.use_roi_mode = False             # placeholder
        self.trigger_mode = "SET_FRAMES"      # placeholder
        self.detector_size_constants = _FakeSizeConstants()

    @property
    def full_filename(self):
        return f"{self.prefix}_{self.run_number}"


class FakeEigerDetector:
    """A source-shaped Eiger over Signal-shaped members; every number is a placeholder."""

    def __init__(self, **_options):
        self._directory = os.path.realpath(tempfile.mkdtemp(prefix="openmhs-dodal-fake-"))
        weakref.finalize(self, shutil.rmtree, self._directory, True)
        self.cam = _FakeCam()
        self.odin = _FakeOdin(self)
        self.bit_depth = _FakeSignal(16)       # placeholder
        self.stale_params = _FakeSignal(0)     # placeholder
        self.detector_params = _FakeDetectorParams(self._directory)
        self.arming_status = _FakeStatus(done=True)   # class attribute upstream: a finished Status (eiger.py:64-65)
        self.disarming_status = None                  # eiger.py:87
        self.collections = 0                   # placeholder: test counter of finished collections
        self.stop_calls = 0                    # placeholder: test counter
        self.stop_cleanups = 0                 # placeholder: test counter of stop calls that ran the cleanup
        self.disarm_calls = 0                  # placeholder: test counter
        # Placeholder starting state: one earlier collection of this acquisition id finished and is on disk.
        self._open_odin_pvs()
        self._writers_start()
        self._writers_finish()

    # -- the fake Odin writers -------------------------------------------------------------------------------------
    def _open_odin_pvs(self):
        prefix = self.detector_params.full_filename
        self.odin.file_writer.file_path.set(self.detector_params.directory)
        self.odin.file_writer.file_name.set(prefix)
        self.odin.meta.file_name.set(prefix)
        self.odin.file_writer.id.set(prefix)

    def _writers_start(self):
        self.odin.file_writer.capture.set(1)
        self.odin.meta.ready.set(1)
        for node in self.odin.nodes.nodes:
            node.writing.set(1)

    def _writers_finish(self):
        if self.odin.writing_finished():
            return
        self.collections += 1
        acquisition = self.odin.file_writer.id.get()
        for suffix, body in (("_000001.h5", b"placeholder frames %d\n"), ("_meta.h5", b"placeholder meta %d\n")):
            with open(os.path.join(self._directory, acquisition + suffix), "wb") as stream:
                stream.write(body % self.collections)   # placeholder bytes, not HDF5
        self.odin.meta.ready.set(0)
        for node in self.odin.nodes.nodes:
            node.writing.set(0)

    # -- the upstream members this package uses ---------------------------------------------------------------------
    def is_armed(self):
        return self.odin.fan.ready.get() == 1 and self.cam.acquire.get() == 1

    def wait_on_arming_if_started(self):
        if not self.arming_status.done:
            self.arming_status.wait(60)

    def async_stage(self):
        self.disarming_status = None
        self.odin.nodes.clear_odin_errors()
        status_ok, error_message = self.odin.wait_for_odin_initialised(10)
        if not status_ok:
            raise Exception(f"Odin not initialised: {error_message}")
        self.arming_status = self.do_arming_chain()
        return self.arming_status

    def do_arming_chain(self):
        assert self.detector_params
        self.odin.stop()
        self._open_odin_pvs()
        self._writers_start()
        self.set_cam_acquire()
        self.filewriters_finished = self.odin.create_finished_status()
        self.odin.fan.ready.set(1)
        return _FakeStatus(done=True)

    def stage(self):
        self.wait_on_arming_if_started()
        if not self.is_armed():
            self.async_stage().wait(60)

    def unstage(self):
        assert self.detector_params is not None
        try:
            self.disarming_status = _FakeStatus(done=False)
            self.wait_on_arming_if_started()
            self.odin.file_writer.start_timeout.set(1).wait(10)
            self._writers_finish()               # placeholder: the collection's frames arrived and were written
            self.filewriters_finished.wait(30)   # AttributeError without a prior arming, as upstream (eiger.py:174)
        finally:
            self.disarm_detector()
            status_ok = self.odin.check_and_wait_for_odin_state(10)
            self.disable_roi_mode().wait(10)
        self.disarming_status.set_finished()
        return status_ok

    def stop(self, *args):
        self.stop_calls += 1
        if self.disarming_status and not self.disarming_status.done:
            self.disarming_status.wait(60)
        elif not self.disarming_status:
            self.disarming_status = _FakeStatus(done=False)
            try:
                self.stop_cleanups += 1
                self.wait_on_arming_if_started()
                stop_status = self.odin.stop()
                self.odin.file_writer.start_timeout.set(1).wait(10)
                self.disarm_detector()
                stop_status &= self.disable_roi_mode()
                stop_status.wait(10)
                self.odin.fan.dev_shm_enable.set(0).wait(10)
            finally:
                self.disarming_status.set_finished()
        # else: upstream logs "Already disarmed, doing nothing" (eiger.py:212-213)

    def disable_roi_mode(self):
        return self.change_roi_mode(False)

    def change_roi_mode(self, enable):
        assert self.detector_params is not None
        constants = self.detector_params.detector_size_constants
        dimensions = constants.roi_size_pixels if enable else constants.det_size_pixels
        self.cam.roi_mode.set(1 if enable else 0, timeout=10).wait(timeout=10)
        self.odin.file_writer.image_height.set(dimensions.height, timeout=10).wait(timeout=10)
        self.odin.file_writer.image_width.set(dimensions.width, timeout=10).wait(timeout=10)
        self.odin.file_writer.num_row_chunks.set(dimensions.height, timeout=10).wait(timeout=10)
        return self.odin.file_writer.num_col_chunks.set(dimensions.width, timeout=10)

    def disarm_detector(self):
        self.disarm_calls += 1
        self.cam.acquire.set(0).wait(10)

    def set_cam_acquire(self):
        return self.cam.acquire.set(1, timeout=10)
