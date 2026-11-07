"""Config-only Driver for the finite controlled MCP client contract."""
from __future__ import annotations

import copy

from .base import Driver, _NativeAttr, _SafeStateAttr
from .families import _FamilyDriver
from .spec import Action, DriverDefinitionError, Field
from .mcp_client_config import compile_mcp_client
from .ophyd_config import model_contract
from ..bridge.base import Bridge, make_mhs_error


def _fields_schema(fields):
    value = {'type': 'object', 'properties': {name: field.to_schema() for name, field in (fields or {}).items()},
            'required': [name for name, field in (fields or {}).items() if field.required is not False],
            'additionalProperties': False}
    _nullable_enums(value)
    return value


def _nullable_enums(value):
    # In this finite compiler a nullable enumerated Field means exactly its
    # listed values plus null; preserve optional upstream no-change values.
    if type(value) is dict:
        if type(value.get('type')) is list and 'null' in value['type'] and 'enum' in value and None not in value['enum']:
            value['enum'].append(None)
        for child in value.values():
            _nullable_enums(child)
    elif type(value) is list:
        for child in value:
            _nullable_enums(child)


def _numeric_limits(fields):
    for field in (fields or {}).values():
        if type(field) is not Field:
            raise DriverDefinitionError('MCP fields must be concrete SDK Field declarations')
        if field.native_unit not in (None,field.unit):
            raise DriverDefinitionError('MCP does not perform undeclared native-unit conversions')
        if field.type in ('number', 'integer') and field.enum is None and not field.limits:
            raise DriverDefinitionError('MCP numeric inputs need source-backed or operator-required limits')
        if field.properties:
            _numeric_limits(field.properties)
        if field.items:
            _numeric_limits({'item': field.items})


def _command_maps(cls):
    from .mcp_client_config import plain
    plain(cls.commands)
    result=copy.deepcopy(cls.commands)
    for cap,binding in result.items():
        if 'input_schema' in binding:
            raise DriverDefinitionError('MCP command schemas are compiled from their Action, not supplied twice')
        if type(cls.actions.get(cap)) is not Action:
            raise DriverDefinitionError('MCP needs an explicit Action for every command')
        binding['input_schema']=_fields_schema(cls.actions[cap].input)
    return result


class McpClientDriver(_FamilyDriver):
    """Finite MCP tool declarations over an injected controlled transport.

    Discovery never expands the declared authority. No native transport is
    implemented; every hardware construction refuses before import or I/O.
    """
    family = 'mcp-client'
    mcp_config = {}

    @classmethod
    def _check_mcp_class(cls):
        protected = {name for base in (McpClientDriver, _FamilyDriver, Driver, Bridge)
                     for name, value in vars(base).items()
                     if callable(value) or isinstance(value, (classmethod, staticmethod, property))}
        protected.difference_update({'native', 'safe_state'})
        for owner in cls.__mro__:
            if owner is McpClientDriver:
                break
            for name, value in vars(owner).items():
                if (name in protected or callable(value) or isinstance(value, (classmethod, staticmethod, property))
                        or (hasattr(type(value), '__get__') and type(value) not in (_NativeAttr, _SafeStateAttr)
                            and name not in ('__dict__', '__weakref__'))):
                    raise DriverDefinitionError('MCP config-only classes cannot override methods: ' + name)
            if vars(owner).get('_needs_instance', False):
                raise DriverDefinitionError('MCP models cannot depend on native instances')
        config = compile_mcp_client(cls.mcp_config, _command_maps(cls), cls.reads, cls.writes)
        if cls.mode != 'hardware' or cls.estop_physical_ref is not None:
            raise DriverDefinitionError('MCP declares hardware with unresolved native admission; fake is a backend choice')
        if cls.safety_bindings:
            raise DriverDefinitionError('MCP safety is the finite mcp_config transaction, not executable bindings')
        for cap, binding in config['commands'].items():
            action = cls.actions.get(cap)
            if type(action) is not Action or action.safe_state:
                raise DriverDefinitionError('MCP actions must be explicit and cannot certify physical safe-state')
            tool = config['tools'][binding['tool']]
            _numeric_limits(action.input)
            output = tool['output']
            if output['kind'] == 'json' and not output.get('artifact'):
                if _fields_schema(action.output) != output['schema']:
                    raise DriverDefinitionError('MCP inline output differs from its exact action schema')
            else:
                fields = action.output or {}
                expected = ({'text'} if output['kind'] == 'text' else
                            {'image_ref', 'width', 'height', 'media_type'} if output['kind'] == 'png' else
                            {'artifact_ref', 'media_type'})
                if set(fields) != expected:
                    raise DriverDefinitionError('MCP primary output must retain the complete text/artifact representation')

    def __init__(self, **kwargs):
        McpClientDriver._check_mcp_class.__func__(type(self))
        if kwargs.get('backend', 'fake') != 'fake':
            from ..bridge.mcp_client import native_unavailable
            native_unavailable()
        super().__init__(**kwargs)

    @classmethod
    def bridge_config(cls, resource_id):
        return compile_mcp_client(cls.mcp_config, _command_maps(cls), cls.reads, cls.writes)

    @classmethod
    def _validation_bridge(cls, model):
        from ..bridge.mcp_client import McpClientBridge
        return McpClientBridge(McpClientDriver.bridge_config.__func__(cls, model.resource_id), validation=True)

    @classmethod
    def _fill_model(cls, model, instance, problems):
        from ..catalog import extension_digest
        _FamilyDriver._fill_model.__func__(cls, model, instance, problems)
        for binding in model.bindings:
            if binding.input_schema is not None:
                _nullable_enums(binding.input_schema)
                _nullable_enums(binding.output_schema)
                binding.schema_digest = extension_digest(binding.input_schema, binding.output_schema)

    @classmethod
    def driver_model(cls):
        McpClientDriver._check_mcp_class.__func__(cls)
        result = _FamilyDriver._family_model.__func__(cls, None)
        model_contract(result)
        return copy.deepcopy(result)

    def _driver_model(self):
        if '_mcp_model' in self.__dict__:
            return McpClientDriver._verified_model(self)
        model = McpClientDriver.driver_model.__func__(type(self))
        self._mcp_config = McpClientDriver.bridge_config.__func__(type(self), model.resource_id)
        self._mcp_model = copy.deepcopy(model)
        self._mcp_contract = model_contract(model)
        self._mcp_runtime_contract = model_contract(self._mcp_config)
        self._mcp_factories = copy.deepcopy(dict(type(self).backends))
        self._mcp_options = copy.deepcopy(self.options)
        return model

    def _verified_model(self):
        current = McpClientDriver.driver_model.__func__(type(self))
        runtime = McpClientDriver.bridge_config.__func__(type(self), current.resource_id)
        if (model_contract(current) != self._mcp_contract or model_contract(self._model) != self._mcp_contract
                or model_contract(self._mcp_model) != self._mcp_contract
                or model_contract(runtime) != self._mcp_runtime_contract
                or model_contract(self._mcp_config) != self._mcp_runtime_contract
                or dict(type(self).backends) != self._mcp_factories or self.options != self._mcp_options):
            raise DriverDefinitionError('MCP model/runtime differs from its immutable declaration')
        return copy.deepcopy(self._mcp_model)

    def _backend_factory(self, backend):
        from .base import _resolve_symbol
        if backend != 'fake':
            from ..bridge.mcp_client import native_unavailable
            native_unavailable()
        factory = self._mcp_factories.get(backend)
        if factory is None:
            raise make_mhs_error('MHS.DEVICE.NOT_READY', 'MCP needs an explicit controlled peer')
        resolved = factory if callable(factory) and not isinstance(factory, str) else _resolve_symbol(str(factory), self._package)
        return lambda **_ignored: resolved(**copy.deepcopy(self._mcp_options))

    def make_bridge(self, native):
        from ..bridge.mcp_client import McpClientBridge
        model = McpClientDriver._verified_model(self)
        return McpClientBridge(copy.deepcopy(self._mcp_config), transport=native,
                               device_id=self.device_id, resource_id=model.resource_id)

    def call(self, capability_id, args=None, ctx=None):
        McpClientDriver._verified_model(self)
        return super().call(capability_id, args, ctx)

    def read(self, resource_id, fields=None, ctx=None):
        McpClientDriver._verified_model(self)
        return super().read(resource_id, fields, ctx)
