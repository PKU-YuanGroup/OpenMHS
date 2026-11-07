"""Config-only controlled SiLA family; every native backend stays refused."""
from __future__ import annotations

import copy

from ..bridge.base import Bridge
from .base import Driver, _NativeAttr, _SafeStateAttr, _resolve_symbol
from .families import _FamilyDriver
from .ophyd_config import model_contract
from .sila2_config import compile_sila2, fingerprint, diagnostic_type, input_schema, plain
from .spec import Action, DriverDefinitionError, Field


def _field_matches(field, spec):
    kinds = {'Boolean': 'boolean', 'Integer': 'integer', 'Real': 'number', 'String': 'string',
             'List': 'array', 'Structure': 'object'}
    if (type(field) is not Field or field.type != kinds.get(spec['type']) or field.nullable
            or field.unit != spec.get('unit') or field.native_unit is not None):
        raise DriverDefinitionError('SiLA Field type/unit differs from its exact declared typed route')
    if spec['type'] == 'List':
        if field.max_items is None or field.max_items > spec['max_items']:
            raise DriverDefinitionError('SiLA list field needs its finite item bound')
        _field_matches(field.items, spec['items'])
    if spec['type'] == 'Structure':
        _fields_match(field.properties or {}, spec['fields'])
    if spec['type'] == 'String' and (field.max_length is None or field.max_length > spec['max_length']):
        raise DriverDefinitionError('SiLA strings require a bounded Field')
    if (field.required is False) != spec.get('optional', False):
        raise DriverDefinitionError('SiLA required/optional declaration differs')
    if spec.get('enum') is not None and field.enum != spec['enum']:
        raise DriverDefinitionError('SiLA enum differs from the finite typed declaration')


def _fields_match(fields, specs):
    if set(fields) != set(specs):
        raise DriverDefinitionError('SiLA fields differ from the complete selected route')
    for name, spec in specs.items():
        _field_matches(fields[name], spec)


class Sila2Driver(_FamilyDriver):
    """Finite typed peer contract with source profiles, not native SiLA support.

    A fake backend factory accepts a PeerLease, registers its peer before any
    initialization, then returns that peer. The class contains data only.
    """
    family = 'sila2'
    sila2_config = {}

    @classmethod
    def _check_sila_class(cls):
        protected = {name for base in (Sila2Driver, _FamilyDriver, Driver, Bridge)
                     for name, value in vars(base).items()
                     if callable(value) or isinstance(value, (classmethod, staticmethod, property))}
        protected.difference_update({'native', 'safe_state'})
        for owner in cls.__mro__:
            if owner is Sila2Driver:
                break
            for name, value in vars(owner).items():
                if (name in protected or callable(value) or isinstance(value, (classmethod, staticmethod, property))
                        or (hasattr(type(value), '__get__') and type(value) not in (_NativeAttr, _SafeStateAttr)
                            and name not in ('__dict__', '__weakref__'))):
                    raise DriverDefinitionError('SiLA config-only classes cannot override methods: ' + name)
        if cls.mode != 'hardware' or cls.risk not in ('R2', 'R3') or cls.estop_physical_ref is not None:
            raise DriverDefinitionError('SiLA selected actuator profiles require R2+ hardware declarations; only fake is admitted')
        config = compile_sila2(cls.sila2_config, cls.commands, cls.reads, cls.writes)
        for capability, binding in config['commands'].items():
            action = cls.actions.get(capability)
            spec = config['members'][binding['member']]
            if type(action) is not Action:
                raise DriverDefinitionError('SiLA commands require explicit Action contracts')
            is_stop = binding['member'] == config['stop']
            if bool(action.safe_state) != is_stop:
                raise DriverDefinitionError('only the explicit Stop binding can claim safe-state behavior')
            if is_stop:
                _fields_match(action.input or {}, {})
                _fields_match(action.output or {}, {'stopped': {'type': 'Boolean'}})
            else:
                _fields_match(action.input or {}, input_schema(config, binding))
                if 'artifact' in binding:
                    expected = {'artifact_ref': {'type': 'String', 'max_length': 4096},
                                'media_type': {'type': 'String', 'max_length': 128}, 'size_bytes': {'type': 'Integer'}}
                    _fields_match(action.output or {}, expected)
                else:
                    _fields_match(action.output or {}, spec['output'])
            if spec['effect'] == 'effectful' and not is_stop:
                if not action.requires_permit or action.risk not in (None, 'R2', 'R3'):
                    raise DriverDefinitionError('effectful SiLA routes require stock input-bound permits and R2+ risk')
                for name, declared in (action.input or {}).items():
                    if not any(limit.is_operator_required for limit in declared.limits):
                        raise DriverDefinitionError('SiLA effect input requires an explicit operator envelope: ' + name)
            if action.cancellable and spec['kind'] != 'observable_command':
                raise DriverDefinitionError('local subscription cancellation is not operation cancellation')
            if spec['kind'] == 'observable_command' and (not action.long_running or action.max_duration_ms is None):
                raise DriverDefinitionError('observable SiLA execution requires a bounded stock operation')
        for name, binding in config['reads'].items():
            spec = diagnostic_type(config, binding) if 'execution' in binding else config['members'][binding['member']]['output'][binding['field']]
            _field_matches(cls.parameters.get(name), spec)
        if cls.safety_bindings != {'estop': {'member': config['stop']}}:
            raise DriverDefinitionError('SiLA requires its explicit acknowledgement-only Stop binding')
        return config

    def __init__(self, **kwargs):
        if kwargs.get('backend', 'fake') != 'fake':
            from ..bridge.sila2 import native_unavailable
            native_unavailable()
        Sila2Driver._check_sila_class.__func__(type(self))
        super().__init__(**kwargs)

    @classmethod
    def bridge_config(cls, resource_id):
        return Sila2Driver._check_sila_class.__func__(cls)

    @classmethod
    def _validation_bridge(cls, model):
        from ..bridge.sila2 import Sila2Bridge
        return Sila2Bridge(Sila2Driver.bridge_config.__func__(cls, model.resource_id), validation=True)

    @classmethod
    def driver_model(cls):
        Sila2Driver._check_sila_class.__func__(cls)
        result = _FamilyDriver._family_model.__func__(cls, None)
        model_contract(result)
        return copy.deepcopy(result)

    def _driver_model(self):
        model = Sila2Driver.driver_model.__func__(type(self))
        self._sila_config = Sila2Driver.bridge_config.__func__(type(self), model.resource_id)
        self._sila_model = copy.deepcopy(model)
        self._sila_authority = model_contract(model)
        self._sila_config_authority = fingerprint(self._sila_config)
        self._sila_factories = dict(type(self).backends)
        plain(self.options)
        self._sila_options = copy.deepcopy(self.options)
        return model

    def _verify(self):
        cls = type(self)
        model = Sila2Driver.driver_model.__func__(cls)
        if (model_contract(model) != self._sila_authority or model_contract(self._model) != self._sila_authority
                or fingerprint(self._sila_config) != self._sila_config_authority
                or fingerprint(Sila2Driver.bridge_config.__func__(cls, model.resource_id)) != self._sila_config_authority
                or fingerprint(self.options) != fingerprint(self._sila_options) or dict(cls.backends) != self._sila_factories):
            raise DriverDefinitionError('SiLA model/runtime authority changed')

    def _backend_factory(self, backend):
        from ..bridge.sila2 import PeerLease, native_unavailable
        if backend != 'fake':
            native_unavailable()
        factory = self._sila_factories.get('fake')
        if factory is None:
            raise DriverDefinitionError('explicit controlled SiLA factory required')
        resolved = factory if callable(factory) and not isinstance(factory, str) else _resolve_symbol(str(factory), self._package)
        return lambda **_ignored: PeerLease(resolved, self._sila_options)

    def make_bridge(self, native):
        from ..bridge.sila2 import Sila2Bridge
        self._verify()
        return Sila2Bridge(self._sila_config, transport=native, device_id=self.device_id, resource_id=self._model.resource_id)

    def call(self, capability_id, args=None, ctx=None):
        self._verify()
        return super().call(capability_id, args, ctx)

    def read(self, resource_id, fields=None, ctx=None):
        self._verify()
        return super().read(resource_id, fields, ctx)

    def estop(self, reason='', ctx=None):
        self._verify()
        return super().estop(reason, ctx)

    def reset(self, ctx=None):
        self._verify()
        return super().reset(ctx)
