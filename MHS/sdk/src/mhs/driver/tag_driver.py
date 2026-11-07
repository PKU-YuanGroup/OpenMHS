"""Config-only tag, register and PV driver (registry family ``tag-bridge``).

A :class:`TagDriver` subclass sets class attributes only: ``tag_config``
(profile, points with source references, timeouts), ``parameters``,
``reads``, ``writes``, ``commands``, ``actions`` and ``safety_bindings``.
:func:`mhs.driver.tag_config.compile_tags` gives their grammar; the runtime is
:class:`mhs.bridge.tags.TagBridge` over an injected transport.

* The fake backend is the package's own fake (usually a
  :class:`mhs.bridge.tag_fake.RecordingTagTransport` subclass).
* A hardware backend is the package's ``native.py`` factory, which builds the
  vendor client and returns a transport object. It never starts without a
  schema-valid ``driver.lock.json`` carrying a human ``reviewed_by`` of scope
  ``hardware``, at every risk class and for every author: address maps are
  deployment specific and an industrial server can front anything. Models keep
  ``reviewed_by`` null.
* A driver with any write or effectful command must declare
  ``safety_bindings["estop"]``: fixed steps and at least one confirmation read.
  Without a real stop route a tag driver can only observe.
* Declarations are copied and fingerprinted when an instance is built; a later
  change of a class attribute, an option or a backend entry refuses every
  operation except the stop.
"""
from __future__ import annotations

import copy
from typing import Any, Mapping

from ..bridge.base import Bridge, make_mhs_error
from .base import Driver, _NativeAttr, _SafeStateAttr, _resolve_symbol
from .families import _FamilyDriver
from .ophyd_config import model_contract
from .spec import Action, DriverDefinitionError
from .tag_config import compile_tags, fingerprint

__all__ = ["TagDriver"]


class TagDriver(_FamilyDriver):
    """Finite tag, register and PV points (Modbus, EPICS Channel Access, ASCOM Alpaca) over a transport.

    Reads become resource state or observation actions, writes become
    ``cap.device.configure.v1`` or fixed/input-bound command steps, and the stop
    is a fixed write or method call confirmed by a fresh read. No vendor library
    is imported by the SDK; hardware needs a human hardware review first.
    """

    family = "tag-bridge"
    tag_config: Mapping[str, Any] = {}

    # -- declaration -----------------------------------------------------------------------
    @classmethod
    def _check_tag_class(cls) -> dict[str, Any]:
        protected = {name for base in (TagDriver, _FamilyDriver, Driver, Bridge)
                     for name, value in vars(base).items()
                     if callable(value) or isinstance(value, (classmethod, staticmethod, property))}
        protected.difference_update({"native", "safe_state"})
        for owner in cls.__mro__:
            if owner is TagDriver:
                break
            for name, value in vars(owner).items():
                if (name in protected or callable(value) or isinstance(value, (classmethod, staticmethod, property))
                        or (hasattr(type(value), "__get__") and type(value) not in (_NativeAttr, _SafeStateAttr)
                            and name not in ("__dict__", "__weakref__"))):
                    raise DriverDefinitionError("tag-bridge config-only classes cannot override methods: " + name)
            if vars(owner).get("_needs_instance", False):
                raise DriverDefinitionError("tag-bridge models cannot depend on a native instance")
        if cls.mode != "hardware":
            raise DriverDefinitionError("a tag device is a hardware declaration; the fake is a backend choice")
        config = compile_tags(cls.tag_config, reads=cls.reads, writes=cls.writes, commands=cls.commands,
                              safety_bindings=cls.safety_bindings)
        actions = dict(cls.actions or {})
        effectful = bool(config["writes"])
        for capability_id, spec in config["commands"].items():
            action = actions.get(capability_id)
            if action is not None and type(action) is not Action:
                raise DriverDefinitionError(f"actions[{capability_id!r}] must be an Action(...)")
            if spec["kind"] == "read":
                if action is not None and (action.safe_state or action.long_running or action.input):
                    raise DriverDefinitionError(f"{capability_id}: an observation takes no input, is not long-running "
                                                "and is never a safe-state action")
                if capability_id.startswith("x-cap.") and (action is None or action.verb != "read"):
                    raise DriverDefinitionError(f"{capability_id}: an x-cap observation needs Action(verb='read')")
                spec["safe_state"] = False
                continue
            effectful = True
            if action is None:
                raise DriverDefinitionError(f"{capability_id}: an effectful tag command needs an explicit Action")
            if action.verb == "read" or action.long_running:
                raise DriverDefinitionError(f"{capability_id}: an effectful tag command is not a read and not "
                                            "long-running in this helper version")
            inputs = {source["input"] for step in spec["steps"]
                      for source in ([step] if "write" in step else list(step["args"].values())) if "input" in source}
            inputs |= {source["input"] for source in spec["result"].values() if "input" in source}
            declared = set(action.input or {})
            if action.safe_state:
                if inputs or declared or not spec["confirm"]:
                    raise DriverDefinitionError(f"{capability_id}: a safe-state action is input-free, writes fixed "
                                                "values and confirms them with at least one read")
            elif not inputs <= declared:
                raise DriverDefinitionError(f"{capability_id}: step inputs {sorted(inputs - declared)} are not "
                                            "declared in the Action input")
            spec["safe_state"] = bool(action.safe_state)
        if effectful and config["estop"] is None:
            raise DriverDefinitionError("a tag driver with writes or effectful commands needs safety_bindings['estop'] "
                                        "(fixed steps and a confirmation read); without a real stop route it may only "
                                        "observe")
        return config

    @classmethod
    def bridge_config(cls, resource_id: str = "main") -> dict[str, Any]:
        return TagDriver._check_tag_class.__func__(cls)

    @classmethod
    def _validation_bridge(cls, model: Any) -> Any:
        from ..bridge.tags import TagBridge

        return TagBridge(TagDriver.bridge_config.__func__(cls, model.resource_id), validation=True)

    @classmethod
    def driver_model(cls) -> Any:
        TagDriver._check_tag_class.__func__(cls)
        result = _FamilyDriver._family_model.__func__(cls, None)
        model_contract(result)
        return copy.deepcopy(result)

    # -- instance ------------------------------------------------------------------------------
    def __init__(self, **kwargs: Any) -> None:
        TagDriver._check_tag_class.__func__(type(self))
        backend = kwargs.get("backend", "fake")
        if backend not in ("fake", "hardware"):
            raise ValueError("a tag driver serves its fake or, after a human hardware review, its hardware backend; "
                             "there is no sim backend")
        super().__init__(**kwargs)
        self._require_hardware_review()

    def _driver_model(self) -> Any:
        if "_tag_model" in self.__dict__:
            return TagDriver._verified_model(self)
        cls = type(self)
        model = TagDriver.driver_model.__func__(cls)
        self._tag_config = TagDriver.bridge_config.__func__(cls, model.resource_id)
        self._tag_model = copy.deepcopy(model)
        self._tag_contract = model_contract(model)
        self._tag_config_print = fingerprint(self._tag_config)
        self._tag_factories = dict(cls.backends or {})
        self._tag_options = copy.deepcopy(self.options)
        return model

    def _verified_model(self) -> Any:
        cls = type(self)
        current = TagDriver.driver_model.__func__(cls)
        runtime = TagDriver.bridge_config.__func__(cls, current.resource_id)
        if (model_contract(current) != self._tag_contract or model_contract(self._model) != self._tag_contract
                or model_contract(self._tag_model) != self._tag_contract
                or fingerprint(runtime) != self._tag_config_print
                or fingerprint(self._tag_config) != self._tag_config_print
                or dict(cls.backends or {}) != self._tag_factories or self.options != self._tag_options):
            raise DriverDefinitionError("tag-bridge model or runtime differs from its declaration at construction")
        return copy.deepcopy(self._tag_model)

    def _require_hardware_review(self) -> None:
        if self.backend != "hardware":
            return
        if not self.is_hardware:
            raise make_mhs_error("MHS.DEVICE.NOT_READY", f"{type(self).__name__} has no hardware backend",
                                 {"retryable": False})
        from .loader import read_lock

        lock, problems = read_lock(self.base_dir)
        reviewer = lock.get("reviewed_by") if isinstance(lock, Mapping) and not problems else None
        if not isinstance(reviewer, Mapping) or reviewer.get("scope") != "hardware":
            raise PermissionError(f"{type(self).__name__}: a tag-bridge hardware backend needs a schema-valid "
                                  "driver.lock.json with a human reviewed_by signature of scope hardware before any "
                                  "factory or connection runs (all risk classes and authors; models keep "
                                  "reviewed_by null)")

    def _backend_factory(self, backend: str) -> Any:
        if backend == "hardware":
            self._require_hardware_review()
        factory = self._tag_factories.get(backend)
        if factory is None:
            raise make_mhs_error("MHS.DEVICE.NOT_READY", f"{type(self).__name__} declares no {backend!r} backend",
                                 {"retryable": False})
        resolved = factory if callable(factory) and not isinstance(factory, str) else _resolve_symbol(str(factory),
                                                                                                     self._package)
        options = copy.deepcopy(self._tag_options)
        return lambda **_ignored: resolved(**copy.deepcopy(options))

    def open_native(self) -> Any:
        self._require_hardware_review()
        return super().open_native()

    def make_bridge(self, native: Any) -> Any:
        from ..bridge.tags import TagBridge

        self._require_hardware_review()
        model = TagDriver._verified_model(self)
        if native is None:
            raise make_mhs_error("MHS.DEVICE.NOT_READY", f"the {self.backend!r} backend produced no tag transport",
                                 {"retryable": False})
        return TagBridge(copy.deepcopy(self._tag_config), transport=native, device_id=self.device_id,
                         resource_id=model.resource_id)

    # -- verified contract operations (the stop is never refused here) ----------------------------
    def call(self, capability_id: str, args: Mapping[str, Any] | None = None, ctx: Any = None) -> Any:
        TagDriver._verified_model(self)
        return super().call(capability_id, args, ctx)

    def read(self, resource_id: str, fields: Any = None, ctx: Any = None) -> Any:
        TagDriver._verified_model(self)
        return super().read(resource_id, fields, ctx)

    def write(self, resource_id: str, patch: Mapping[str, Any], ctx: Any = None) -> Any:
        TagDriver._verified_model(self)
        return super().write(resource_id, patch, ctx)

    def reset(self, ctx: Any = None) -> Any:
        TagDriver._verified_model(self)
        return super().reset(ctx)
