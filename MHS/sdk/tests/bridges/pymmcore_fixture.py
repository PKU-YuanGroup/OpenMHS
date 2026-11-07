"""Controlled camera/core shape. No ImSwitch, pymmcore, GUI or native import.

acquireSingleFrame preserves the selected method's one-frame sequence, buffer
first polling and finally-stop order. Hooks model native delays/faults; this
fixture is not source or binary evidence for the upstream constructor.
"""
import threading
import time

from mhs.bridge.pymmcore_camera import CameraFactory, CameraProfile


class CameraScenario:
    def __init__(self, frame, pixel_format="mono8"):
        self.frame, self.pixel_format = frame, pixel_format
        self.trace, self.hooks = [], {}
        self.core = self.manager = None
        self.status = "done"
        self.available = True
        self.forced_layout = None
        self.ignore_cancel = False
        self.fail_readback = False

    def hit(self, stage, *args):
        self.trace.append((stage, *args))
        hook = self.hooks.get(stage)
        if hook is not None:
            hook(*args)

    def create(self, lease):
        self.hit("core_creation")
        self.core = CameraCore(self)
        lease.register_core(self.core)
        self.hit("registered")
        self.core.loadDevice(lease.camera, "DemoCamera", "DCam")
        self.core.initializeDevice(lease.camera)
        self.manager = CameraManager(self.core, lease.camera)
        self.hit("manager_constructed")
        return self.manager

    def factory(self):
        return CameraFactory(self.create, CameraCore, CameraManager)

    def profile(self, **kwargs):
        values = dict(camera="Camera", pixel_format=self.pixel_format,
                      exposure_min_ms=0.1, exposure_max_ms=100,
                      timeout_ms=500, stop_timeout_ms=60,
                      sensor_width=12, sensor_height=8, binning_values=(1, 2))
        values.update(kwargs)
        return CameraProfile(**values)

    def counts(self, stage):
        return sum(row[0] == stage for row in self.trace)


class CameraCore:
    def __init__(self, scenario):
        self.scenario = scenario
        self.loaded, self.label = [], ""
        self.running, self.ready = False, False
        self.exposure, self.binning = 1.0, 1
        self.height, self.width = scenario.frame.shape[:2]
        self.roi = (0, 0, self.width, self.height)
        self.auto_shutter, self.shutter = False, ""

    def loadDevice(self, label, adapter, device):
        self.loaded.append(label)
        self.label = label
        self.scenario.hit("load", label, adapter, device)

    def initializeDevice(self, label):
        self.scenario.hit("initialize", label)

    def getLoadedDevices(self):
        self.scenario.hit("devices")
        return tuple(self.loaded)

    def getCameraDevice(self):
        return self.label

    def getAutoShutter(self):
        return self.auto_shutter

    def getShutterDevice(self):
        return self.shutter

    def getImageWidth(self):
        self.scenario.hit("geometry")
        return self.width

    def getImageHeight(self):
        return self.height

    def getExposure(self):
        self.scenario.hit("exposure_read")
        return self.exposure

    def getBytesPerPixel(self):
        layout = self.scenario.forced_layout
        return layout[0] if layout else {"mono8": 1, "mono16": 2, "rgb8": 4}[self.scenario.pixel_format]

    def getNumberOfComponents(self):
        layout = self.scenario.forced_layout
        return layout[1] if layout else (4 if self.scenario.pixel_format == "rgb8" else 1)

    def isSequenceRunning(self, label=None):
        self.scenario.hit("running", label)
        if label is not None and label not in self.loaded:
            raise ValueError("missing camera label")
        return self.running

    def getROI(self, label):
        assert label == self.label
        return self.roi

    def getProperty(self, label, name):
        assert (label, name) == (self.label, "Binning")
        return str(self.binning)

    def clearCircularBuffer(self):
        self.scenario.hit("clear")
        self.ready = False

    def getRemainingImageCount(self):
        self.scenario.hit("poll")
        return int(self.ready)

    def startSequenceAcquisition(self, count, interval, overflow):
        self.scenario.hit("start", count, interval, overflow)
        self.running, self.ready = True, self.scenario.available

    def stopSequenceAcquisition(self, label=None):
        self.scenario.hit("stop", label)
        self.running = False

    def popNextImage(self):
        self.scenario.hit("pop")
        if not self.ready:
            raise ValueError("no frame")
        self.ready = False
        return self.scenario.frame

    def setExposure(self, value):
        self.scenario.hit("set_exposure", value)
        if not self.scenario.fail_readback:
            self.exposure = value

    def setROI(self, label, x, y, width, height):
        self.scenario.hit("set_roi", label, x, y, width, height)
        if not self.scenario.fail_readback:
            self.roi = (x, y, width, height)
            self.width, self.height = width, height

    def setProperty(self, label, name, value):
        self.scenario.hit("set_binning", label, name, value)
        if not self.scenario.fail_readback:
            self.binning = int(value)

    def unloadDevice(self, label):
        self.scenario.hit("unload", label)
        self.loaded.remove(label)

    def reset(self):
        raise AssertionError("global reset is never a camera recovery path")


class CameraManager:
    def __init__(self, core, label):
        core.scenario.hit("manager_init")
        self._core, self._label = core, label
        self._running, self._triggerMode = False, "software"
        self._grabLock, self._exclusiveLock = threading.Lock(), threading.Lock()
        self._exclusiveOwner = None
        self._latest = None

    def acquireExclusive(self, owner, timeout=0.0):
        self._core.scenario.hit("claim", owner, timeout)
        if not self._exclusiveLock.acquire(blocking=False):
            return False
        self._exclusiveOwner = owner
        if self._core.isSequenceRunning():
            self._core.stopSequenceAcquisition()
        return True

    def releaseExclusive(self, owner=None, restoreLive=None):
        self._core.scenario.hit("release", owner, restoreLive)
        if self._exclusiveOwner != owner:
            return
        self._exclusiveOwner = None
        self._exclusiveLock.release()
        if restoreLive:
            raise AssertionError("release must not restart live view")

    def acquireSingleFrame(self, cancelEvent=None, timeout=None, pollInterval=0.05):
        with self._grabLock:
            self._core.scenario.hit("acquire_entry")
            try:
                if self._core.isSequenceRunning():
                    self._core.stopSequenceAcquisition()
                self._running = False
            except Exception:
                pass
            try:
                self._core.clearCircularBuffer()
            except Exception:
                pass
            try:
                self._core.startSequenceAcquisition(1, 0, True)
            except Exception:
                return None, "error"
            deadline = time.time() + timeout
            status = self._core.scenario.status
            try:
                while True:
                    if self._core.getRemainingImageCount() > 0:
                        break
                    if cancelEvent.is_set() and not self._core.scenario.ignore_cancel:
                        status = "cancelled"
                        break
                    if time.time() > deadline:
                        status = "timeout"
                        break
                    time.sleep(pollInterval)
            finally:
                try:
                    if self._core.isSequenceRunning():
                        self._core.stopSequenceAcquisition()
                except Exception:
                    pass
            if status != "done":
                return self._latest, status
            image = self._core.popNextImage()
            self._latest = image
            return image, "done"

    def setParameter(self, name, value):
        assert name == "Exposure"
        try:
            self._core.setExposure(value)
        except Exception:
            pass
        return value

    def crop(self, x, y, width, height):
        try:
            self._core.setROI(self._label, x, y, width, height)
        except Exception:
            pass

    def setBinning(self, value):
        try:
            self._core.setProperty(self._label, "Binning", str(value))
        except Exception:
            pass

    def snapSync(self):
        raise AssertionError("cached fallback is not the selected single-frame route")

    def getLatestFrame(self):
        raise AssertionError("preview is not primary acquisition")
