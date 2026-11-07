"""Finite camera family; native admission is intentionally unavailable.

The fake backend returns a CameraFactory declaration without constructing its
camera. The bridge invokes that declaration only inside retained construction.
This module imports no NumPy, ImSwitch or native dependency.
"""
from __future__ import annotations

import copy
import json

from ..bridge.base import make_mhs_error
from ..bridge.pymmcore_camera import CAPTURE, CameraFactory, CameraProfile, PymmcoreCameraBridge
from . import model as _model
from .families import _FamilyDriver, _parameters
from .spec import Action, DriverDefinitionError, Field, Limit

__all__ = ["PymmcorePlusDriver", "CameraProfile", "CameraFactory"]


class PymmcorePlusDriver(_FamilyDriver):
    """One labelled camera, complete primary pixels and finite configuration.

Subclasses declare camera_profile and a fake backend that returns CameraFactory.
The profile's exposure envelope is mandatory operator data; a fake example is
not a hardware safety limit. Hardware/sim admission stays refused while the
selected ImSwitch factory, binaries and adapter stop contract remain unproven.
"""
    family = "pymmcore-plus"
    camera_profile: CameraProfile | None = None
    native = "imswitch.imcontrol.model.managers.detectors.MMCoreDetectorManager:MMCoreDetectorManager"
    safe_state = "The owned, explicitly labelled camera sequence is stopped; no optical safety is inferred."

    def __init__(self, **kwargs):
        protected = {"driver_model", "_family_model", "_fill_model", "_driver_model", "__init__", "open_native",
                     "make_bridge", "_get_native", "_set_native", "inner", "call", "read", "write", "estop",
                     "safe_state", "reset", "close", "setup", "teardown", "_check_authority", "_authority"}
        for owner in type(self).__mro__:
            if owner is PymmcorePlusDriver:
                break
            if protected.intersection(vars(owner)):
                raise DriverDefinitionError("camera family subclasses are data-only; runtime hook overrides are unsupported")
        super().__init__(**kwargs)
        self._camera_model_owner = self._model
        self._camera_profile_owner = self._camera_profile
        self._camera_backends_owner = self._camera_backends
        self._camera_backend_values = tuple(self._camera_backends.items())
        self._camera_backend = self.backend
        self._camera_model_signature = self._authority()

    def _authority(self):
        return json.dumps({"resource": self._model.resource_manifest(), "safety": self._model.safety_manifest(),
                           "bindings": [binding.manifest(self._model.resource_id) for binding in self._model.bindings],
                           "native": self._model.native_symbol, "mode": self._model.mode},
                          sort_keys=True, allow_nan=False)

    def _check_authority(self):
        if (self._model is not self._camera_model_owner or self._camera_profile is not self._camera_profile_owner
                or self._camera_backends is not self._camera_backends_owner or self.backend != self._camera_backend
                or self.options or self._authority() != self._camera_model_signature
                or set(self._camera_backends) != {key for key, _ in self._camera_backend_values}
                or any(self._camera_backends[key] is not value for key, value in self._camera_backend_values)):
            raise DriverDefinitionError("camera model/construction authority changed after resolution")

    @classmethod
    def driver_model(cls):
        return copy.deepcopy(cls._family_model(None))

    @classmethod
    def _fill_model(cls, model, instance, problems):
        p = cls.camera_profile
        if type(p) is not CameraProfile:
            problems.append("camera_profile requires an exact immutable CameraProfile with operator exposure bounds")
            return
        if cls._native_symbol != PymmcorePlusDriver._native_symbol:
            problems.append("this camera helper supports only the declared ImSwitch MMCoreDetectorManager route")
        if any(dict(getattr(cls, name) or {}) for name in ("commands", "reads", "writes", "parameters", "actions", "safety_bindings")):
            problems.append("camera routes and schemas are finite; arbitrary family maps are unsupported")
        params = {
            "camera": Field("string", enum=[p.camera]),
            "width": Field("integer", nullable=True), "height": Field("integer", nullable=True),
            "exposure_ms": Field("number", unit="ms", nullable=True, writable=True,
                                 description="Verified camera exposure time; changing it requires the local operator envelope.",
                                 limit=Limit.operator_required("Supply the local camera/specimen exposure envelope.")),
            "acquiring": Field("boolean", nullable=True), "state_stale": Field("boolean"),
        }
        if p.binning_values:
            params["binning"] = Field("integer", unit="1", nullable=True, writable=True,
                                      description=f"Camera binning factor; supported choices are {list(p.binning_values)}.",
                                      limit=Limit.operator_required("Supply the allowed camera binning envelope."))
        if p.sensor_width is not None:
            params["roi"] = Field("object", nullable=True, writable=True,
                                  description="Camera ROI in sensor pixels: x, y, width and height; no software crop is applied.",
                                  properties={name: Field("integer", unit="1", required=True,
                                      description=f"ROI {name} in sensor pixels.",
                                      limit=Limit.operator_required("Supply the allowed camera ROI envelope."))
                                      for name in ("x", "y", "width", "height")})
        model.params = _parameters(params, problems)
        configure = _model.configure_binding(model.params, problems)
        capture = Action(name="capture", exclusive=True, cancellable=False,
                         max_duration_ms=p.timeout_ms,
                         input={"camera": Field(enum=[p.camera], description="The fixed camera label; another camera is refused."),
                                "format": Field(enum=["png"], description="Lossless primary pixels in PNG format."),
                                "width": Field("integer", unit="1", description="Assert the current image width in pixels; does not resize.",
                                               limit=Limit.operator_required("Supply the allowed capture width envelope.")),
                                "height": Field("integer", unit="1", description="Assert the current image height in pixels; does not resize.",
                                                limit=Limit.operator_required("Supply the allowed capture height envelope.")),
                                "exposure_ms": Field("number", unit="ms",
                                    description="Assert the freshly observed exposure time; does not change it.",
                                    limit=Limit.operator_required("Supply the local camera/specimen exposure envelope."))},
                         description="Acquire one complete frame through acquireSingleFrame; geometry/exposure inputs assert current settings.")
        model.bindings = [configure, _model.binding_from_action(CAPTURE, capture, problems)]
        model.estop = _model.EstopModel(None, "CMMCorePlus.stopSequenceAcquisition(camera_label)")
        model.interlocks = []

    def _driver_model(self):
        self._camera_profile = type(self).camera_profile
        self._camera_backends = dict(type(self).backends or {})
        return type(self).driver_model()

    def open_native(self):
        self._check_authority()
        if self.backend != "fake":
            raise make_mhs_error("MHS.DEVICE.NOT_READY", "native camera admission is unresolved (B01-B10)", {"retryable": False})
        if self.options:
            raise DriverDefinitionError("camera factory options are not an arbitrary native constructor channel")
        from .base import _resolve_symbol
        target = self._camera_backends.get("fake")
        if isinstance(target, str):
            target = _resolve_symbol(target, self._package)
        plan = target() if callable(target) else target
        if type(plan) is not CameraFactory:
            raise DriverDefinitionError("the fake backend must return a CameraFactory declaration, not construct a camera")
        return plan

    def make_bridge(self, native):
        self._check_authority()
        from ..testing import Recorder, log_of
        record_log = None
        if type(native) is Recorder:
            record_log = log_of(native)
            native = object.__getattribute__(native, "_mhs_target")
        if type(native) is not CameraFactory:
            raise DriverDefinitionError("camera injection requires a CameraFactory, never a borrowed core/manager")
        return PymmcoreCameraBridge(self._camera_profile, native, backend=self.backend,
                                   resource_id=self._model.resource_id, device_id=self.device_id, record_log=record_log)

    def read(self, resource_id, fields=None, ctx=None):
        self._check_authority()
        state = super().read(resource_id, fields, ctx)
        return {name: value for name, value in state.items() if self._model.param(name) is not None}

    def call(self, capability_id, args=None, ctx=None):
        self._check_authority()
        return super().call(capability_id, args, ctx)

    def write(self, resource_id, patch, ctx=None):
        self._check_authority()
        return super().write(resource_id, patch, ctx)
