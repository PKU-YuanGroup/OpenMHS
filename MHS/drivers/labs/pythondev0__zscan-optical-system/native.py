"""Hardware backend: checked adapter for the SDK calls in upstream ``camera:ThorlabsCamera``.

Used only with backend="hardware" and allow_hardware=True (an operator decision).  This package is model-authored and
unreviewed and declares risk R0: the loader refuses a model-authored hardware backend only at R2 and R3, so this
package claims no such protection. The acceptance gate runs the fake backend and tests this module with
SDK-shaped stubs; it never imports the upstream clone or vendor SDK. Nothing here ran against a camera.

The upstream repository is a flat source tree, not an installable package: ``camera.py`` imports ``ueye`` from
``pyueye`` (``camera.py:5``) and defines ``ThorlabsCamera`` at ``camera.py:9``.  Two deployment choices are therefore
explicit:

* ``source_root`` is the path of the pinned clone root that contains ``camera.py``.  When it is given, this factory
  loads that file by path (it does not modify the clone and does not install anything).  When it is omitted, the
  module must already be importable as ``camera`` from the operator's PYTHONPATH.
* ``device_id`` selects the handle as in the upstream constructor. Its default 0 is the constructor default (``camera.py:20``),
  not a statement about which camera is attached; the deployment selects the uEye device.

``pyueye`` and the IDS uEye SDK must already be installed (``README.md:85``); the card's install command only installs
the Python requirements. The adapter imports that module for its SDK dependencies but does not call its
constructor or capture method. The upstream discards statuses from color mode, allocation, active-memory
selection, capture and release (``camera.py:39-72``). ``_CheckedCamera`` follows those calls and arguments,
checks each against IS_SUCCESS (the source's initialization predicate at ``camera.py:35-37``), and refuses
a failed freeze before copying any buffer. It avoids the upstream constructor/release stdout prints.
IS_WAIT remains a blocking capture with no source-backed finite deadline; the endpoint can time out but
cannot abort that SDK call. Deployments disable Python bytecode writes when the source tree is read-only.
"""

import importlib.util
import os

from mhs.driver import DriverFailed


class _CheckedCamera:
    """Source-shaped camera.py:27-72 adapter that checks every SDK status.

    Dependencies come from the deployment's pinned camera module. No upstream constructor or method is
    called: those methods discard allocation/capture failures and print to stdout. This adapter keeps
    their handle, buffer, Mono8, blocking-freeze and reshape arguments, with explicit failure handling.
    """

    def __init__(self, ueye, reshape, device_id=0):
        self._ueye = ueye
        self._reshape = reshape
        self.h_cam = ueye.HIDS(device_id)
        self.width, self.height = 1280, 1024  # camera.py:28-29
        self.mem_ptr, self.mem_id = ueye.c_mem_p(), ueye.INT()
        self._allocated = False
        self._connected = False
        self._check(ueye.is_InitCamera(self.h_cam, None), "is_InitCamera")
        self._connected = True
        try:
            self._check(ueye.is_SetColorMode(self.h_cam, ueye.IS_CM_MONO8), "is_SetColorMode")
            self._check(ueye.is_AllocImageMem(self.h_cam, self.width, self.height, 8,
                                             self.mem_ptr, self.mem_id), "is_AllocImageMem")
            self._allocated = True
            self._check(ueye.is_SetImageMem(self.h_cam, self.mem_ptr, self.mem_id), "is_SetImageMem")
        except Exception:
            try:
                self.release()
            except Exception:
                pass  # preserve the construction failure after attempting both cleanup operations
            raise

    def _check(self, code, operation):
        if code != self._ueye.IS_SUCCESS:
            raise DriverFailed("MHS.DEVICE.FAULTED", f"{operation} failed with SDK status {code}")

    def capture_image(self):
        if not self._connected or not self._allocated:
            raise DriverFailed("MHS.DEVICE.NOT_READY", "camera memory is not active")
        self._check(self._ueye.is_FreezeVideo(self.h_cam, self._ueye.IS_WAIT), "is_FreezeVideo")
        data = self._ueye.get_data(self.mem_ptr, self.width, self.height, 8, self.width, copy=True)
        return self._reshape(data, (self.height, self.width))

    def release(self):
        # Exit is attempted even when freeing memory fails; neither status is reported as success.
        failure = None
        if self._allocated:
            try:
                self._check(self._ueye.is_FreeImageMem(self.h_cam, self.mem_ptr, self.mem_id), "is_FreeImageMem")
                self._allocated = False
            except Exception as exc:
                failure = exc
        if self._connected:
            try:
                self._check(self._ueye.is_ExitCamera(self.h_cam), "is_ExitCamera")
                self._connected = False
                self._allocated = False
            except Exception as exc:
                if failure is None:
                    failure = exc
        if failure is not None:
            raise failure


def _load_from_source(source_root):
    """Load the pinned flat camera module without changing sys.path; deployment controls bytecode writes."""
    root = os.path.realpath(os.fspath(source_root))
    path = os.path.join(root, "camera.py")
    if not os.path.isfile(path):
        raise FileNotFoundError(f"source_root does not contain the upstream camera.py: {path}")
    spec = importlib.util.spec_from_file_location("_zscan_upstream_camera", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load the upstream camera module from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def connect(device_id=0, *, source_root=None, **options):
    """Use camera.py's SDK dependencies with checked statuses; ``device_id`` selects the uEye device."""
    if options:
        raise TypeError(f"unknown connection option(s): {', '.join(sorted(options))}")
    if source_root is None:
        import camera as upstream
    else:
        upstream = _load_from_source(source_root)
    return _CheckedCamera(upstream.ueye, upstream.np.reshape, device_id=int(device_id))
