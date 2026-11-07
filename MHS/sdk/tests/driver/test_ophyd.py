"""Configuration and pinned-source rejection boundaries; no Ophyd import."""
import copy
from pathlib import Path
from types import SimpleNamespace
import unittest
from mhs.driver import Field,OphydDriver,DriverDefinitionError
from mhs.driver.ophyd_config import signal_specs,compile_signals
from mhs.driver.ophyd_check import prove_signal,UnresolvedIdentity
from mhs.driver.loader import import_driver_module

FIXTURE = Path(__file__).resolve().parents[1] / 'fixtures' / 'ophyd_axis'
MOVE = 'x-cap.sdk-fixture.axis_move.v1'

SPEC={'signal':'velocity','get':True,'set':True,'profile':'classic_epics_v1',
      'get_kwargs':{'use_monitor':False},'timeout_ms':100,'source_ref':'device.py:4'}
SOURCE='from ophyd import Component as Cpt, EpicsSignal, Device\n\nclass Axis(Device):\n    velocity = Cpt(EpicsSignal, "V")\n'
class Tree:
    def __init__(self,text):self.text=text
    def read_text(self,path):return self.text if path=='device.py' else None
class ConfigTests(unittest.TestCase):
    def test_explicit_compilation_and_copy(self):
        fields={'speed':Field('number',writable=True)};spec=copy.deepcopy(SPEC)
        reads,writes=compile_signals({'speed':spec},fields,{},{});spec['get_kwargs']['use_monitor']=True
        self.assertEqual(reads['speed']['args'],{'use_monitor':{'value':False}})
        self.assertEqual(writes['speed'],{'native':'velocity.set','invoke':'status','timeout_ms':100})
    def test_invalid_configuration_refused(self):
        mutations=[('signal','x[0]'),('signal','_private'),('signal','x.__dict__'),('get',1),('set',1),
                   ('get_kwargs',{}),('get_kwargs',{'use_monitor':0}),('timeout_ms',True),('timeout_ms',0),
                   ('timeout_ms',60001),('source_ref','../device.py:4'),('source_ref','device.py'),
                   ('profile','guess'),('extra',True)]
        for key,value in mutations:
            spec=copy.deepcopy(SPEC);spec[key]=value
            with self.subTest(key=key,value=value),self.assertRaises(DriverDefinitionError):
                signal_specs({'speed':spec},{'speed':Field('number',writable=True)})
    def test_ambiguous_maps_refused(self):
        with self.assertRaises(DriverDefinitionError):compile_signals({'speed':SPEC},{'speed':Field('number',writable=True)},{'speed':'x'},{})
        other=copy.deepcopy(SPEC);other['signal']='velocity.inner'
        with self.assertRaises(DriverDefinitionError):signal_specs({'speed':SPEC,'other':other},{'speed':Field('number',writable=True),'other':Field('number',writable=True)})
    def test_no_shared_model_config_or_factory_options(self):
        made=[]
        def factory(**kwargs):made.append(kwargs);return object()
        class Axis(OphydDriver):
            device_id='axis';device_kind='motion.axis';mode='hardware';risk='R1'
            native='device:Axis';parameters={'speed':Field('number',unit='mm/s',writable=True)}
            signal_bindings={'speed':copy.deepcopy(SPEC)};backends={'fake':factory}
        options={'marker':{'x':1}};first=Axis(backend='fake',options=options)
        options['marker']['x']=2;first.options['marker']['x']=3
        Axis.signal_bindings['speed']['get_kwargs']['use_monitor']=True
        self.assertEqual(first._runtime_bridge_config(object())['reads']['main']['fields']['speed']['args'],{'use_monitor':{'value':False}})
        first._backend_factory('fake')(**first.options);self.assertEqual(made,[{'marker':{'x':1}}])
        first._driver_model().params[0].field.unit='deg/s'
        self.assertEqual(first._driver_model().params[0].field.unit,'mm/s')

class ProofTests(unittest.TestCase):
    def prove(self,text=SOURCE,spec=None):return prove_signal(Tree(text),SimpleNamespace(classes=['device.py:Axis']),spec or SPEC)
    def test_explicit_component(self):self.assertEqual(self.prove(),'velocity')
    def test_non_component_factories_and_shadowing(self):
        for text in (SOURCE.replace('Cpt(EpicsSignal','dict(EpicsSignal'),SOURCE+'Cpt = dict\n',
                     SOURCE+'EpicsSignal.get = lambda self: 7\n',SOURCE+'Axis.__init__ = lambda self: None\n',
                     SOURCE.replace('    velocity =','    Cpt = dict\n    velocity ='),
                     SOURCE.replace('    velocity =','    EpicsSignal = dict\n    velocity =')):
            with self.subTest(text=text),self.assertRaises(ValueError):self.prove(text)
    def test_instance_replacement_and_prefix_mutation(self):
        methods=['self.velocity = object()','self.velocity.get = lambda: 7','alias = self.velocity\n        alias.set = lambda v: None',
                 'self.alias = self.velocity','x = [self.velocity]','setattr(self,"velocity",object())',
                 'getattr(self,"velocity").get = lambda: 1','self.__dict__["velocity"] = object()',
                 'self = object()','alias = self\n        alias.velocity = object()']
        for body in methods:
            text=SOURCE+'    def mutate(self):\n        '+body+'\n'
            with self.subTest(body=body),self.assertRaises(ValueError):self.prove(text)
    def test_dynamic_declarations_and_inaccurate_refs(self):
        for text in (SOURCE.replace('"V"','str("V")'),SOURCE.replace('class Axis(Device):','@decorate\nclass Axis(Device):'),
                     SOURCE+'    __init__ = make_init()\n',SOURCE+'    def __getattr__(self,name): return None\n'):
            with self.subTest(text=text),self.assertRaises(ValueError):self.prove(text)
        for patch in ({'source_ref':'device.py:2'},{'signal':'motor.velocity'}):
            spec={**SPEC,**patch}
            with self.assertRaises(ValueError):self.prove(spec=spec)

    def test_receiver_escapes_are_machine_unresolved(self):
        for body in ('helper(self)','helper(self.velocity)','getattr(self,name).__init__("other")',
                     'self.velocity.__init__("other")','return self.velocity','get = getattr\n        get(self,name)','helper({"axis":self})','self.__dict__.update({})'):
            with self.subTest(body=body),self.assertRaises(UnresolvedIdentity):
                self.prove(SOURCE+'    def change(self,name):\n        '+body+'\n')
    def test_constructor_alias_and_class_body_mutation_refused(self):
        for suffix in ('Alias = Axis\nAlias.__init__ = lambda self: None\n',
                       'Alias = EpicsSignal\nAlias.get = lambda self: 8\n',
                       'bag = [EpicsSignal]\n',
                       '    setattr(velocity,"get",lambda:8)\n'):
            with self.subTest(suffix=suffix),self.assertRaises(ValueError):self.prove(SOURCE+suffix)


class HardwareViewTests(unittest.TestCase):
    def fixture(self):
        from pathlib import Path
        from mhs.driver.loader import driver_class
        from mhs.driver.check import _hardware_view_subject
        path=FIXTURE
        driver=driver_class(path)(backend='fake')
        self.addCleanup(driver.close)
        ctx=SimpleNamespace(cls=type(driver),instance=driver)
        return driver,ctx,_hardware_view_subject
    def test_explicit_units_preserve_hardware_view_without_factory(self):
        from mhs.driver.build import build_manifest
        d,ctx,subject=self.fixture();self.assertFalse(d._native_ready)
        manifest=build_manifest(subject(ctx),backend='hardware')
        self.assertFalse(d._native_ready)
        self.assertEqual(manifest['mode'],'hardware')
    def test_instance_cannot_lower_hardware_risk_mode_or_safe_state(self):
        for member,value in (('risk','R1'),('mode','simulated'),('safe_state','imagined safe')):
            d,ctx,subject=self.fixture();setattr(d._model,member,value)
            with self.subTest(member=member),self.assertRaises(DriverDefinitionError):subject(ctx)
    def test_instance_cannot_remove_limits_actions_or_stop(self):
        for mutation in ('limit','action','stop','parameter'):
            d,ctx,subject=self.fixture()
            if mutation=='limit':
                next(b for b in d._model.bindings if b.capability_id=='cap.device.configure.v1').limits={}
            elif mutation=='action':d._model.bindings=[b for b in d._model.bindings if not b.safe_state]
            elif mutation=='stop':d._model.estop=None
            else:d._model.params=[]
            with self.subTest(mutation=mutation),self.assertRaises(DriverDefinitionError):subject(ctx)

    def test_unsigned_hardware_refused_before_native_import(self):
        import sys,tempfile
        from pathlib import Path
        from unittest.mock import patch
        from mhs.adapter import load_driver,LoadError
        path=FIXTURE
        from mhs.driver.loader import read_lock
        lock,problems=read_lock(path)
        self.assertEqual(problems,[])
        self.assertEqual(lock['authored_by']['kind'],'model')
        self.assertIsNone(lock['reviewed_by'])
        module=import_driver_module(path);before_calls=list(module.native_connect_calls)
        before={key for key in sys.modules if key.startswith(('ophyd','ophyd_devices'))}
        with tempfile.TemporaryDirectory() as directory, patch.object(
                module,'connect_native',side_effect=AssertionError('native admission sentinel')) as factory:
            with self.assertRaises(LoadError) as raised:
                load_driver(path,backend='hardware',allow_hardware=True,state_dir=directory,
                            options={'engineering_unit':'mm','velocity_unit':'mm/s','prefix':'NO-IOC:'})
            factory.assert_not_called()
        self.assertEqual(raised.exception.reason,'review_required')
        self.assertEqual(module.native_connect_calls,before_calls)
        self.assertEqual({key for key in sys.modules if key.startswith(('ophyd','ophyd_devices'))},before)


class AncestryTests(unittest.TestCase):
    def test_unknown_external_constructor_not_assumed_to_preserve_component(self):
        with self.assertRaises(UnresolvedIdentity):
            ProofTests().prove(SOURCE.replace('from ophyd import Component as Cpt, EpicsSignal, Device',
                'from ophyd import Component as Cpt, EpicsSignal; from unknown_runtime import Device'))

class V2SourceIdentityTests(unittest.TestCase):
    prove = ProofTests.prove
    def test_reviewer_reflection_and_decorator_counterexamples(self):
        bodies = [
            '    __getattribute__ = None\n', '    __setattr__ = None\n',
            '    def mutate(self):\n        self.__setattr__("velocity", object())\n',
            '    def mutate(self):\n        self.__delattr__("velocity")\n',
            '    def mutate(self):\n        self.__getattribute__("velocity").get = lambda: 99\n',
            '    def mutate(self):\n        super().__getattribute__("velocity").get = lambda: 99\n',
            '    staticmethod = 1\n    @staticmethod\n    def corrupt(self):\n        pass\n',
            '    classmethod = 1\n    @classmethod\n    def corrupt(cls):\n        pass\n',
            '    __dict__ = {}\n', '    __slots__ = ()\n',
            '    def mutate(self):\n        get = object.__getattribute__\n',
        ]
        self.assertEqual(self.prove(), 'velocity')
        for body in bodies:
            with self.subTest(body=body), self.assertRaises(ValueError):self.prove(SOURCE + body)
        for tail in ('from builtins import getattr as load\n',
                     'import builtins as b\nlookup = b.getattr\n',
                     'import builtins as b\nlookup = b.__dict__\n'):
            with self.subTest(tail=tail), self.assertRaises(ValueError):self.prove(SOURCE + tail)

class V2ContractTests(unittest.TestCase):
    fixture = HardwareViewTests.fixture
    def test_every_resolved_schema_and_execution_field_is_preserved(self):
        mutations = [
            lambda m:setattr(m.bindings[-1], 'requires_permit', not m.bindings[-1].requires_permit),
            lambda m:setattr(m.bindings[-1], 'risk', 'R0'),
            lambda m:setattr(m.bindings[-1], 'input_schema', {'type':'object'}),
            lambda m:setattr(m.bindings[-1], 'output_schema', {'type':'object'}),
            lambda m:setattr(m.bindings[0], 'input_schema', {'type':'object'}),
            lambda m:setattr(m.params[0].field, 'type', 'string'),
            lambda m:setattr(m.params[0].field, 'unit', 's'),
            lambda m:setattr(m.params[0].field, 'native_unit', 'm'),
            lambda m:setattr(m.estop, 'native', 'fake_stop'),
            lambda m:setattr(m, 'watchdog_ms', 10),
            lambda m:setattr(m, 'estop_latency_ms', 10),
            lambda m:setattr(m, 'native_symbol', 'other:Axis'),
        ]
        for mutate in mutations:
            d,ctx,subject=self.fixture();mutate(d._model)
            with self.subTest(mutate=mutate),self.assertRaises(DriverDefinitionError):subject(ctx)
            self.assertFalse(d._native_ready)

    def test_published_projection_is_exact_and_detached(self):
        from mhs.driver.build import build_manifest
        d,ctx,subject=self.fixture();projection=subject(ctx)
        before=build_manifest(projection,backend='hardware',instance_id='stable-fixture')
        d._model.bindings.clear();d._model.params.clear()
        self.assertEqual(build_manifest(projection,backend='hardware',instance_id='stable-fixture'),before)
        with self.assertRaises(DriverDefinitionError):subject(ctx)

    def test_author_hook_cannot_weaken_class_authority_during_build(self):
        d,ctx,_=self.fixture();Base=type(d)
        class Mutates(Base):
            actions=copy.deepcopy(Base.actions)
            @classmethod
            def _fill_model(cls,model,instance,problems):
                next(action for action in cls.actions.values() if action.name=='move_absolute').requires_permit=False
                Base._fill_model.__func__(cls,model,instance,problems)
        next(action for action in Mutates.actions.values() if action.name=='move_absolute').requires_permit=True
        with self.assertRaises(DriverDefinitionError):Mutates(backend='fake')

    def test_unset_fixed_and_conversion_unit_contracts(self):
        from mhs.driver.ophyd_config import compile_unit_metadata
        from mhs.driver import Limit
        binding={'parameters.value':'unit'}
        params={'value':Field('number',unit='mm')}
        result,_,_=compile_unit_metadata(params,{},binding,{}, {'unit':'mm'},'hardware')
        self.assertEqual(result['value'].unit,'mm');self.assertIsNot(result['value'],params['value'])
        for fields,options in ((params,{'unit':'m'}),(params,{}),
            ({'value':Field('number',unit='mm',native_unit='m')},{'unit':'mm'}),
            ({'value':Field('number',limit=Limit(min=0,max=1,source='upstream_code',ref='x.py:1'))},{'unit':'mm'})):
            with self.subTest(fields=fields,options=options),self.assertRaises(DriverDefinitionError):
                compile_unit_metadata(fields,{},binding,{},options,'hardware')
        self.assertEqual(compile_unit_metadata({'value':Field('number')},{},binding,{'unit':'mm'},{},'fake')[0]['value'].unit,'mm')
        with self.assertRaises(DriverDefinitionError):
            compile_unit_metadata({'value':Field('number')},{},binding,{'unit':'mm'},{},'hardware')

class V2StockPermitTests(unittest.TestCase):
    def test_declared_permit_blocks_move_and_weakened_model_refuses_construction(self):
        from mhs.driver.build import build_manifest,device_from_manifest
        from mhs.driver.check import _hardware_view_subject
        from mhs.server import MHSServer
        mod=import_driver_module(FIXTURE)
        for weaken in (False,True):
            class Variant(mod.Driver):pass
            Variant.__module__=mod.Driver.__module__
            Variant.actions=copy.deepcopy(mod.Driver.actions)
            Variant.actions[mod.MOVE].requires_permit=True
            @classmethod
            def fill(cls,model,instance,problems):
                mod.Driver._fill_model.__func__(cls,model,instance,problems)
                if weaken:next(b for b in model.bindings if b.capability_id==mod.MOVE).requires_permit=False
            Variant._fill_model=fill
            if weaken:
                with self.assertRaises(DriverDefinitionError):Variant(backend='fake')
                continue
            d=Variant(backend='fake')
            manifest=build_manifest(_hardware_view_subject(SimpleNamespace(cls=Variant,instance=d)),backend='hardware')
            server=MHSServer('mhs://localhost',[device_from_manifest(manifest,d)],strict=True,armed=True,site_limits=mod.overlay())
            try:
                client=mod.Client(server);client.read();raw=d.inner._target
                receipt=client.command(mod.MOVE,{'position':.2})
                self.assertEqual(receipt['status'],'rejected')
                self.assertEqual(receipt['error']['mhs_code'],'MHS.SAFETY.PERMIT_INVALID')
                self.assertEqual([c for c in raw.calls if c[0]=='move'],[])
            finally:server.close();d.close()

class FixtureBackendTests(unittest.TestCase):
    """Fixture qualification only; BEC containment remains in its package tests."""

    def test_effectful_fake_and_explicit_units_through_stock_server(self):
        from mhs.driver.build import build_manifest,device_from_manifest
        from mhs.server import MHSServer
        d,ctx,subject=HardwareViewTests().fixture()
        mod=import_driver_module(FIXTURE)
        model=d._driver_model()
        self.assertEqual({p.name:p.field.unit for p in model.params},
                         {'position':'mm','setpoint':'mm','velocity':'mm/s','done':None,'engineering_unit':None})
        manifest=build_manifest(subject(ctx),backend='hardware')
        server=MHSServer('mhs://localhost',[device_from_manifest(manifest,d)],strict=True,
                         armed=True,site_limits=mod.overlay())
        try:
            client=mod.Client(server);client.read();raw=d.inner._target
            move=client.command(mod.MOVE,{'position':.2})
            self.assertEqual(move['status'],'completed',move)
            self.assertEqual(move['output'],{'completed':True})
            self.assertEqual(client.write(.3)['status'],'completed')
            self.assertEqual(client.read()['state']['position'],.2)
            self.assertEqual(client.read()['state']['velocity'],.3)
            self.assertEqual([c for c in raw.calls if c[0]=='move'],[('move',.2,False,1.0)])
            self.assertEqual([c for c in raw.calls if c[0]=='velocity.set'],[('velocity.set',.3)])
            self.assertEqual(client.command(mod.STOP)['output'],{'stopped':True,'done':1,'position':.2})
            before=[call for call in raw.calls if call[0] in ('move','velocity.set')]
            self.assertEqual(client.command(mod.MOVE,{'position':2.})['status'],'rejected')
            self.assertEqual(client.write(2.)['status'],'rejected')
            self.assertEqual([call for call in raw.calls if call[0] in ('move','velocity.set')],before)
        finally:server.close();d.close()

    def test_even_valid_live_configuration_cannot_import_upstream(self):
        import sys
        d,ctx,_=HardwareViewTests().fixture()
        try:
            module=import_driver_module(FIXTURE)
            before={name for name in sys.modules if name.startswith(('ophyd','ophyd_devices'))}
            with self.assertRaisesRegex(RuntimeError,'SDK fixture has no live backend'):
                module.connect_native(engineering_unit='mm',velocity_unit='mm/s',prefix='NO-IOC:')
            self.assertEqual({name for name in sys.modules if name.startswith(('ophyd','ophyd_devices'))},before)
        finally:d.close()

class V3ReceiverTests(unittest.TestCase):
    prove=ProofTests.prove
    def test_ordinary_and_positional_only_self_positive(self):
        for method in ('    def read(self):\n        return self.velocity.get()\n',
                       '    def read(self, /):\n        return self.velocity.get()\n',
                       '    def __init__(self, /, *args, **kwargs):\n        super().__init__(*args, **kwargs)\n',
                       '    @property\n    def reading(self):\n        return self.velocity.get()\n'):
            with self.subTest(method=method):self.assertEqual(self.prove(SOURCE+method),'velocity')
    def test_unsupported_receiver_forms_refuse_instead_of_spelling_bypass(self):
        for method in ('    def __init__(axis, *args, **kwargs):\n        super().__init__(*args, **kwargs)\n        axis.velocity.get = lambda: 99\n',
                       '    def corrupt(axis):\n        axis.velocity.get = lambda: 99\n',
                       '    def corrupt(axis, /):\n        axis.velocity.get = lambda: 99\n',
                       '    def corrupt(*axes):\n        axes[0].velocity.get = lambda: 99\n',
                       '    def corrupt(*, self):\n        pass\n',
                       '    @staticmethod\n    def corrupt(axis):\n        axis.velocity.get = lambda: 99\n',
                       '    @classmethod\n    def corrupt(cls):\n        cls.velocity.get = lambda: 99\n',
                       '    def corrupt(self, argument=EpicsSignal("OTHER")):\n        pass\n',
                       '    def corrupt(self, velocity):\n        velocity.get = lambda: 99\n',
                       '    def corrupt(self, axis):\n        alias = axis\n        alias.velocity.get = lambda: 99\n'):
            with self.subTest(method=method),self.assertRaises(ValueError):self.prove(SOURCE+method)
    def test_positional_only_receiver_mutation_still_refuses(self):
        with self.assertRaises(ValueError):
            self.prove(SOURCE+'    def corrupt(self, /):\n        self.velocity.get = lambda: 99\n')


class V4SignalUseTests(unittest.TestCase):
    prove = ProofTests.prove

    def test_direct_operations_results_and_string_metadata_remain_supported(self):
        bodies = (
            'return self.velocity.get()',
            'return self.velocity.set(value)',
            'self.velocity.put(value)',
            'samples = [self.velocity.get() for _ in range(2)]\n        return samples',
            'if (reading := self.velocity.get()) is not None:\n            return reading',
            'label = self.velocity.name\n        return label',
            'return self.velocity.pvname',
            'return [self.velocity.name, self.velocity.pvname]',
            'return str(self.velocity.name)',
            'self.velocity.name = "axis_velocity"',
        )
        for body in bodies:
            with self.subTest(body=body):
                self.assertEqual(self.prove(SOURCE + '    def operation(self, value=None):\n        ' + body + '\n'), 'velocity')

    def test_signal_and_bound_method_escape_forms_are_unresolved(self):
        bodies = (
            'for signal in [self.velocity]:\n            signal.get = lambda **kwargs: 99',
            'if (signal := self.velocity) is not None:\n            signal.get = lambda **kwargs: 99',
            'signals = [signal for signal in (self.velocity,)]',
            'signals = (signal for signal in [self.velocity])',
            'for get in [self.velocity.get]:\n            get()',
            'if (get := self.velocity.get) is not None:\n            get()',
            'with self.velocity as signal:\n            signal.get = lambda: 99',
            'match self.velocity:\n            case signal:\n                signal.get = lambda: 99',
            'signal = self.velocity',
            'get = self.velocity.get',
            'return lambda: self.velocity',
            'return self.velocity.get',
            'return self.velocity.name()',
            'self.velocity.other_method()',
            'sink = {"signal": self.velocity}',
            'return self.velocity.get.cached',
        )
        for body in bodies:
            with self.subTest(body=body), self.assertRaises(UnresolvedIdentity):
                self.prove(SOURCE + '    def operation(self):\n        ' + body + '\n')

    def test_gate_does_not_approve_member_after_unsupported_flow(self):
        from mhs.driver.ophyd_check import check_ophyd_surface
        for body in ('for signal in [self.velocity]:\n            signal.get = lambda: 99',
                     'if (signal := self.velocity) is not None:\n            signal.get = lambda: 99'):
            source = SOURCE + '    def __init__(self, *args, **kwargs):\n        super().__init__(*args, **kwargs)\n        ' + body + '\n'
            errors = []
            gate = SimpleNamespace(error=lambda *args: errors.append(args))
            cls = SimpleNamespace(signal_bindings={'speed': copy.deepcopy(SPEC)},
                                  parameters={'speed': Field('number', writable=True)})
            ctx = SimpleNamespace(cls=cls, tree=Tree(source),
                                  logs=[SimpleNamespace(found_paths={'velocity.get', 'velocity.set'})])
            check_ophyd_surface(ctx, gate, SimpleNamespace(classes=['device.py:Axis']))
            self.assertIn('OPHYD_IDENTITY_UNRESOLVED', [error[0] for error in errors])
            self.assertEqual([error[2] for error in errors if error[0] == 'OPHYD_UNPROVEN_MEMBER'],
                             ['velocity.get', 'velocity.set'])

class V3RuntimeConfigTests(unittest.TestCase):
    fixture=HardwareViewTests.fixture
    def test_full_native_runtime_mapping_cannot_diverge_from_model(self):
        base,_,_=self.fixture();Base=type(base)
        for field in ('estop','close','read','write','command'):
            class Redirect(Base):
                @classmethod
                def bridge_config(cls,resource_id,target='mhs.driver._natives:validation'):
                    config=super().bridge_config(resource_id,target)
                    if field=='estop':config['safety_bindings']['estop']['native']='destroy'
                    elif field=='close':config['close']='stop'
                    elif field=='read':config['reads']['main']['fields']['position']['native']='velocity.get'
                    elif field=='write':config['writes'][resource_id]['params']['velocity']['native']='user_setpoint.put'
                    else:config['capabilities'][MOVE]['native']='destroy'
                    return config
            with self.subTest(field=field),self.assertRaises(DriverDefinitionError):Redirect(backend='fake')
    def test_runtime_construction_and_output_schema_hooks_refused(self):
        base,_,_=self.fixture();Base=type(base)
        for name in ('_runtime_bridge_config','make_bridge','_schemas','_backend_factory','_driver_model'):
            Variant=type('Alternate',(Base,),{name:lambda *a,**k:None})
            with self.subTest(name=name),self.assertRaisesRegex(DriverDefinitionError,'hook overrides'):
                Variant(backend='fake')
    def test_runtime_snapshot_mutation_refuses_hardware_projection(self):
        d,ctx,subject=self.fixture();d._ophyd_config['safety_bindings']['estop']['native']='destroy'
        with self.assertRaisesRegex(DriverDefinitionError,'runtime mapping'):subject(ctx)
        self.assertFalse(d._native_ready)
    def test_mutation_of_factory_or_options_during_model_hook_refuses(self):
        base,_,_=self.fixture();Base=type(base)
        for change in ('factory','options'):
            class Variant(Base):
                backends=copy.deepcopy(Base.backends)
                @classmethod
                def _fill_model(cls,model,instance,problems):
                    Base._fill_model.__func__(cls,model,instance,problems)
                    if change=='factory':cls.backends['fake']=lambda **kwargs:object()
                    else:instance.options['undeclared_native_selection']='other'
            with self.subTest(change=change),self.assertRaises(DriverDefinitionError):Variant(backend='fake')


# --- classic_epics_ro_v1: the get-only EpicsSignalRO profile (OPHYD-READ-ONLY-PROFILE) ---------------------------
RO_SPEC = {'signal': 'readback', 'get': True, 'set': False, 'profile': 'classic_epics_ro_v1',
           'get_kwargs': {'use_monitor': False}, 'timeout_ms': 100, 'source_ref': 'device.py:4'}
RO_SOURCE = ('from ophyd import Component as Cpt, EpicsSignalRO, Device\n\n'
             'class Gauge(Device):\n    readback = Cpt(EpicsSignalRO, "RBV", kind="hinted")\n')


class ReadOnlyProfileTests(unittest.TestCase):
    def prove(self, text=RO_SOURCE, spec=None):
        return prove_signal(Tree(text), SimpleNamespace(classes=['device.py:Gauge']), spec or RO_SPEC)

    def test_get_only_compilation_has_fresh_read_and_no_write(self):
        reads, writes = compile_signals({'pressure': copy.deepcopy(RO_SPEC)}, {'pressure': Field('number')}, {}, {})
        self.assertEqual(reads['pressure'], {'native': 'readback.get', 'invoke': 'call', 'timeout_ms': 100,
                                             'args': {'use_monitor': {'value': False}}})
        self.assertEqual(writes, {})

    def test_set_and_cached_reads_are_refused_at_definition(self):
        refused = (({'set': True}, Field('number', writable=True)),
                   ({'get_kwargs': {}}, Field('number')),
                   ({'get_kwargs': {'use_monitor': True}}, Field('number')),
                   ({'get_kwargs': {'use_monitor': 0}}, Field('number')),
                   ({'profile': 'classic_epics_ro_v2'}, Field('number')),
                   ({'profile': ['classic_epics_ro_v1']}, Field('number')))
        for patch, field in refused:
            spec = {**copy.deepcopy(RO_SPEC), **patch}
            with self.subTest(patch=patch), self.assertRaises(DriverDefinitionError):
                signal_specs({'pressure': spec}, {'pressure': field})

    def test_explicit_read_only_component_proves(self):
        self.assertEqual(self.prove(), 'readback')
        self.assertEqual(self.prove(RO_SOURCE.replace('from ophyd import Component as Cpt, EpicsSignalRO, Device',
                                                      'from ophyd import Component as Cpt, Device\n'
                                                      'from ophyd.signal import EpicsSignalRO')
                                    .replace('device.py:4', 'device.py:5'),
                                    {**RO_SPEC, 'source_ref': 'device.py:5'}), 'readback')

    def test_profile_and_component_type_must_match_exactly(self):
        epics_source = RO_SOURCE.replace('EpicsSignalRO', 'EpicsSignal')
        soft_source = RO_SOURCE.replace('EpicsSignalRO', 'Signal')
        writable = {**RO_SPEC, 'profile': 'classic_epics_v1'}
        soft = {**RO_SPEC, 'profile': 'classic_soft_v1', 'get_kwargs': {}}
        for text, spec in ((RO_SOURCE, writable), (RO_SOURCE, soft), (epics_source, RO_SPEC), (soft_source, RO_SPEC),
                           (RO_SOURCE.replace('from ophyd import', 'from ophyd.areadetector import'), RO_SPEC)):
            with self.subTest(text=text, profile=spec['profile']), self.assertRaises(ValueError):
                self.prove(text, spec)

    def test_forged_writable_read_only_item_is_refused_by_the_proof(self):
        with self.assertRaises(ValueError):
            self.prove(spec={**RO_SPEC, 'set': True})

    def test_shadowing_aliasing_and_escape_of_the_read_only_type_are_refused(self):
        for text in (RO_SOURCE.replace('    readback =', '    EpicsSignalRO = dict\n    readback ='),
                     RO_SOURCE + 'EpicsSignalRO.get = lambda self, **kwargs: 7\n',
                     RO_SOURCE + 'Alias = EpicsSignalRO\n',
                     RO_SOURCE + 'bag = [EpicsSignalRO]\n'):
            with self.subTest(text=text), self.assertRaises(ValueError):
                self.prove(text)
        with self.assertRaises(UnresolvedIdentity):
            self.prove(RO_SOURCE + '    def leak(self):\n        return self.readback\n')

    def test_gate_approves_only_the_get_operation(self):
        from mhs.driver.ophyd_check import check_ophyd_surface
        errors = []
        gate = SimpleNamespace(error=lambda *args: errors.append(args))
        cls = SimpleNamespace(signal_bindings={'pressure': copy.deepcopy(RO_SPEC)}, parameters={'pressure': Field('number')})
        ctx = SimpleNamespace(cls=cls, tree=Tree(RO_SOURCE),
                              logs=[SimpleNamespace(found_paths={'readback.get', 'readback.set', 'readback.put'})])
        check_ophyd_surface(ctx, gate, SimpleNamespace(classes=['device.py:Gauge']))
        self.assertEqual(sorted(error[2] for error in errors if error[0] == 'OPHYD_UNPROVEN_MEMBER'),
                         ['readback.put', 'readback.set'])
        self.assertEqual([error for error in errors if error[0] != 'OPHYD_UNPROVEN_MEMBER'], [])


class FamilyScaffoldTests(unittest.TestCase):
    """`mhs.driver new --like` for a card whose helper is OphydDriver or QcodesDriver (python-object templates)."""

    def test_helper_cards_use_the_python_object_templates(self):
        from mhs.driver.package import card_kind
        self.assertEqual(card_kind({'helper': 'OphydDriver'}), 'python-object')
        self.assertEqual(card_kind({'helper': 'QcodesDriver'}), 'python-object')
        self.assertEqual(card_kind({'helper': None}), 'direct')

    def test_new_like_scaffolds_an_ophyd_card(self):
        import json, tempfile
        from mhs.driver.package import scaffold
        card = {'package_id': 'gh.example/ophyd-device', 'helper': 'OphydDriver', 'family': 'ophyd',
                'upstream': {'repo_url': 'https://github.com/example/ophyd-device', 'commit': '0' * 40,
                             'license_spdx': 'MIT'},
                'entry_symbols': [{'symbol': 'device:Axis', 'file': 'device.py', 'line': 3}],
                'safety': {'risk_floor': 'R1', 'expected_mode': 'hardware'}}
        for helper in ('OphydDriver', 'QcodesDriver'):
            with self.subTest(helper=helper), tempfile.TemporaryDirectory() as directory:
                card_path = Path(directory) / 'card.json'
                card_path.write_text(json.dumps({**card, 'helper': helper}), encoding='utf-8')
                written = scaffold(Path(directory) / 'pkg', card=card_path, like=FIXTURE,
                                   values={'model_id': 'test-model', 'run_id': 'run-1'})
                names = {path.name for path in written}
                self.assertTrue({'driver.py', 'driver.lock.json', 'facts.md', 'test_driver.py', 'task.json'} <= names)
                lock = json.loads((Path(directory) / 'pkg' / 'driver.lock.json').read_text(encoding='utf-8'))
                self.assertEqual(lock['backends'], {'hardware': '.native:connect', 'fake': '.fake:FakeOphydDevice'})
                self.assertIsNone(lock['reviewed_by'])
