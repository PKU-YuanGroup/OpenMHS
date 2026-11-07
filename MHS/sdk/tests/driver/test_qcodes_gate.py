"""Pinned source proof never accepts arbitrary get/set or cache members."""
from __future__ import annotations
import copy
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from mhs.driver import Field
from mhs.driver.check import Gate
from mhs.driver.qcodes_check import check_qcodes_surface
from mhs.driver.upstream import UpstreamTree, class_surface
from mhs.testing.recorder import RecordLog

SOURCE = '''from qcodes.parameters import Parameter
class Native:
    def __init__(self):
        self.channel.frequency = Parameter(name="frequency", get_cmd="F?", set_cmd=self.set_frequency)
        self.power = make(self)
    def set_frequency(self, value): pass
def make(self):
    power = Parameter(name="power", get_cmd="P?", set_cmd=self.set_power)
    power.__doc__ = "RF power"
    return power
class Unrelated:
    def __init__(self):
        self.wrong = Parameter(name="wrong", get_cmd="W?", set_cmd=self.set_wrong)
'''


class QcodesGateTests(unittest.TestCase):
    def check(self, source=SOURCE, *, selector="channel.frequency", source_ref="native.py:4", factory=None, paths=()):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp); (root/'native.py').write_text(source)
            tree=UpstreamTree(root,use_git=False)
            item={"parameter":selector,"get":True,"set":True,"timeout_ms":20,"source_ref":source_ref}
            if factory: item['factory_ref']=factory
            cls=SimpleNamespace(parameters={"value":Field("number",writable=True)},parameter_bindings={"value":item})
            log=RecordLog('native'); log.found_paths.update(paths)
            gate=Gate('G7','Native source')
            check_qcodes_surface(SimpleNamespace(cls=cls,tree=tree,logs=[log]),gate,
                                 class_surface(tree,'native:Native'))
            return [f.code for f in gate.findings if f.severity=='error']

    def test_exact_nested_parameter_and_operations(self):
        self.assertEqual(self.check(paths=['channel','channel.frequency','channel.frequency.get','channel.frequency.set']),[])

    def test_same_file_factory_returning_parameter(self):
        self.assertEqual(self.check(selector='power',source_ref='native.py:5',factory='native.py:7'),[])

    def test_stale_wrong_or_unrelated_reference(self):
        for ref in ('native.py:3','native.py:13','absent.py:4'):
            with self.subTest(ref=ref): self.assertIn('G7.QCODES_PARAMETER_SOURCE',self.check(source_ref=ref))
        self.assertIn('G7.QCODES_PARAMETER_SOURCE',self.check(selector='wrong',source_ref='native.py:13'))

    def test_cache_only_or_disabled_parameter_does_not_prove_measurement(self):
        for command in ('None','False','self.cache.get','self.get_latest'):
            self.assertIn('G7.QCODES_PARAMETER_SOURCE',self.check(SOURCE.replace('get_cmd="F?"','get_cmd='+command)))

    def test_arbitrary_get_set_and_shadowed_constructor_are_rejected(self):
        self.assertIn('G7.QCODES_PARAMETER_SOURCE',self.check(SOURCE.replace('from qcodes.parameters','from unrelated')))
        self.assertIn('G7.QCODES_PARAMETER_SOURCE',self.check(SOURCE.replace('def __init__(self):','def __init__(self, Parameter):')))
        self.assertIn('G7.QCODES_PARAMETER_SOURCE',self.check(SOURCE+'\nParameter = unrelated\n'))
        self.assertIn('G7.QCODES_PARAMETER_SOURCE',self.check(SOURCE.replace('self.channel.frequency = Parameter','self.channel.frequency = Handle')))

    def test_reimport_and_nested_unused_assignment_do_not_prove_parameter(self):
        self.assertIn('G7.QCODES_PARAMETER_SOURCE',self.check(SOURCE+'\nfrom other import Parameter\n'))
        nested=SOURCE.replace('        self.channel.frequency = Parameter',
            '        def unused(self):\n            self.channel.frequency = Parameter')
        self.assertIn('G7.QCODES_PARAMETER_SOURCE',self.check(nested,source_ref='native.py:5'))

    def test_unbounded_or_substituted_factory_is_rejected(self):
        for source in (SOURCE.replace('return power','return other'),SOURCE.replace('return power','return transform(power)'),
                       SOURCE.replace('return power','power = arbitrary()\n    return power')):
            self.assertIn('G7.QCODES_PARAMETER_SOURCE',self.check(source,selector='power',source_ref='native.py:5',factory='native.py:7'))

    def test_observed_cache_or_unconfigured_nested_path_is_not_exempt(self):
        for path in ('channel.frequency.cache','channel.frequency.cache.get','channel.frequency.get_latest','other.get','channel.frequency.set_raw'):
            self.assertIn('G7.QCODES_UNDECLARED_MEMBER',self.check(paths=[path]))

    def test_set_on_declared_get_only_parameter_is_not_allowed(self):
        # Direct proof still includes native set command, but absent declared set
        # must not turn a get/set-looking method into an approved call.
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);(root/'native.py').write_text(SOURCE);tree=UpstreamTree(root,use_git=False)
            cls=SimpleNamespace(parameters={'value':Field('number')},parameter_bindings={'value':{
                'parameter':'channel.frequency','get':True,'set':False,'timeout_ms':20,'source_ref':'native.py:4'}})
            log=RecordLog('native');log.found_paths.add('channel.frequency.set');gate=Gate('G7','native')
            check_qcodes_surface(SimpleNamespace(cls=cls,tree=tree,logs=[log]),gate,class_surface(tree,'native:Native'))
            self.assertEqual([f.code for f in gate.findings],['G7.QCODES_UNDECLARED_MEMBER'])

    def test_factory_name_must_resolve_at_the_call_site(self):
        cases = [SOURCE.replace('def __init__(self):','def __init__(self, make):'),
                 SOURCE+'\nmake = unrelated_factory\n',
                 SOURCE+'\nif True:\n    make = unrelated_factory\n',
                 SOURCE.replace('self.power = make(self)','self.power = make(self)\n        make = other'),
                 SOURCE.replace('def make(self):','@replace\ndef make(self):')]
        for source in cases:
            with self.subTest(source=source):
                self.assertIn('G7.QCODES_PARAMETER_SOURCE',self.check(source,selector='power',source_ref='native.py:5',factory='native.py:7'))

    def test_all_lexical_parameter_binding_forms_are_refused(self):
        sources = [SOURCE.replace('def __init__(self):', 'def __init__(self, *Parameter):'),
                   SOURCE.replace('def __init__(self):', 'def __init__(self, **Parameter):')]
        for suffix in ('if True:\n    Parameter = other', 'for Parameter in values:\n    pass',
                       'try:\n    pass\nexcept Exception as Parameter:\n    pass',
                       'with something as Parameter:\n    pass',
                       'match value:\n    case {"item": Parameter}: pass',
                       'if (Parameter := other): pass', 'del Parameter', 'Parameter.get = other'):
            sources.append(SOURCE+'\n'+suffix+'\n')
        for source in sources:
            with self.subTest(source=source): self.assertIn('G7.QCODES_PARAMETER_SOURCE',self.check(source))

    def test_conditional_or_nonconstructor_assignment_is_not_proof(self):
        for guard in ('if False:', 'if ready:', 'for item in items:', 'try:'):
            source=SOURCE.replace('        self.channel.frequency = Parameter',
                                  '        '+guard+'\n            self.channel.frequency = Parameter')
            if guard=='try:':source=source.replace('        self.power = make(self)','        finally: pass\n        self.power = make(self)')
            with self.subTest(guard=guard): self.assertIn('G7.QCODES_PARAMETER_SOURCE',self.check(source,source_ref='native.py:5'))
        self.assertIn('G7.QCODES_PARAMETER_SOURCE',self.check(SOURCE.replace('def __init__(self):','def unused(self):')))

    def test_selector_prefix_member_and_alias_mutations_are_not_proof(self):
        for statement in ('self.channel.frequency.get = self.get_latest',
                          'self.channel.frequency.set = other', 'self.channel = other',
                          'self.channel.frequency += other', 'del self.channel.frequency',
                          'setattr(self.channel.frequency, "get", other)',
                          'setattr(self.channel, name, other)',
                          'self.channel.frequency.__dict__["get"] = other',
                          'self.__dict__["channel"] = other',
                          'alias = self.channel.frequency',
                          'if ready:\n            self.channel.frequency.get = other'):
            source=SOURCE.replace('self.power = make(self)',statement)
            with self.subTest(statement=statement): self.assertIn('G7.QCODES_PARAMETER_SOURCE',self.check(source))

    def test_cross_file_descendant_and_base_mutations_are_not_ignored(self):
        base='from qcodes.parameters import Parameter\nclass Base:\n    def __init__(self):\n        self.power = Parameter(name="power",get_cmd="P?",set_cmd="P {}")\n'
        for mutation in ('self.power = NotAParameter()', 'self.power.get = self.get_latest',
                         'if ready:\n            self.power.set = other'):
            native='from base import Base\nclass Native(Base):\n    def __init__(self):\n        super().__init__()\n        '+mutation+'\n'
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as temp:
                root=Path(temp);(root/'base.py').write_text(base);(root/'native.py').write_text(native)
                tree=UpstreamTree(root,use_git=False)
                cls=SimpleNamespace(parameters={'power':Field('number',writable=True)},parameter_bindings={'power':{
                    'parameter':'power','get':True,'set':True,'timeout_ms':20,'source_ref':'base.py:4'}})
                gate=Gate('G7','native')
                check_qcodes_surface(SimpleNamespace(cls=cls,tree=tree,logs=[]),gate,class_surface(tree,'native:Native'))
                self.assertIn('G7.QCODES_PARAMETER_SOURCE',[f.code for f in gate.findings])

    def test_class_scope_compound_override_is_not_ignored(self):
        source=SOURCE.replace('class Native:', 'class Native:\n    if True:\n        channel = other')
        self.assertIn('G7.QCODES_PARAMETER_SOURCE',self.check(source,source_ref='native.py:6'))

    def test_unused_base_initializer_and_rebound_base_are_refused(self):
        base='from qcodes.parameters import Parameter\nclass Base:\n    def __init__(self):\n        self.power = Parameter(name="power",get_cmd="P?",set_cmd="P {}")\n'
        for native in ('from base import Base\nclass Native(Base):\n    def __init__(self): pass\n',
                       'from base import Base\nif True: Base = other\nclass Native(Base): pass\n'):
            with self.subTest(native=native), tempfile.TemporaryDirectory() as temp:
                root=Path(temp);(root/'base.py').write_text(base);(root/'native.py').write_text(native)
                tree=UpstreamTree(root,use_git=False)
                cls=SimpleNamespace(parameters={'power':Field('number',writable=True)},parameter_bindings={'power':{
                    'parameter':'power','get':True,'set':True,'timeout_ms':20,'source_ref':'base.py:4'}})
                gate=Gate('G7','native')
                check_qcodes_surface(SimpleNamespace(cls=cls,tree=tree,logs=[]),gate,class_surface(tree,'native:Native'))
                self.assertIn('G7.QCODES_PARAMETER_SOURCE',[f.code for f in gate.findings])

    def test_effective_initializer_class_identity_and_reachability_grammar(self):
        base = 'from qcodes.parameters import Parameter\nclass Native:\n    def __init__(self):\n        self.power = Parameter(name="power", get_cmd="P?", set_cmd="P {}")\n'
        cases = [
            (base + '    __init__ = other\n', 4),
            (base + '    if True:\n        __init__ = other\n', 4),
            (base + '    locals()["__init__"] = other\n', 4),
            (base.replace('class Native:', '@replacement\nclass Native:'), 5),
            (base.replace('class Native:', 'class Native(metaclass=Replacement):'), 4),
            (base.replace('        self.power', '        return\n        self.power'), 5),
            (base.replace('        self.power', '        raise RuntimeError()\n        self.power'), 5),
            (base.replace('        self.power', '        if ready: return\n        self.power'), 5),
            (base.replace('        self.power', '        self = other\n        self.power'), 5),
            (base + '        self = other\n', 4),
            (base + '        del self\n', 4),
            (base + '\nAlias = Native\nAlias.__init__ = other\n', 4),
            (base + '\nglobals()["Native"] = other\n', 4),
        ]
        for source, line in cases:
            with self.subTest(source=source):
                self.assertIn('G7.QCODES_PARAMETER_SOURCE', self.check(source, selector='power', source_ref=f'native.py:{line}'))
        self.assertEqual(self.check(base, selector='power', source_ref='native.py:4'), [])

    def test_selected_identity_cannot_escape_via_containers_calls_or_receivers(self):
        base = 'from qcodes.parameters import Parameter\nclass Native:\n    def __init__(self):\n        self.power = Parameter(name="power", get_cmd="P?", set_cmd="P {}")\n'
        for statement in ('alias, = (self.power,)', 'aliases = [self.power]',
                          'mapping = {"power": self.power}', 'alias = (self.power if ready else other)',
                          'replace(self.power)', 'alias = self', 'aliases = [self]',
                          'getattr(self, "power").get = other', 'object.__setattr__(self, "power", other)',
                          'self.__dict__.update(power=other)', 'self.power.replace_get(other)',
                          'return self.power'):
            source = base + '        ' + statement + '\n'
            with self.subTest(statement=statement):
                self.assertIn('G7.QCODES_PARAMETER_SOURCE', self.check(source, selector='power', source_ref='native.py:4'))
        source = base + '    def later(other_self):\n        other_self.power.get = other\n'
        self.assertIn('G7.QCODES_PARAMETER_SOURCE', self.check(source, selector='power', source_ref='native.py:4'))
        # Native Parameter invocation and explicit get/set stay valid uses.
        source = base + '    def later(self):\n        self.power(1)\n        return self.power.get()\n'
        self.assertEqual(self.check(source, selector='power', source_ref='native.py:4'), [])

    def test_constructor_and_factory_identities_cannot_escape_through_aliases(self):
        for suffix in ('\nAlias = Parameter\nAlias.get = other\n',
                       '\naliases = [Parameter]\naliases[0].get = other\n',
                       '\ndef mutate():\n    Parameter.get = other\n',
                       '\nalias = make\nalias.__code__ = other\n',
                       '\ndef mutate():\n    global Parameter\n    Parameter = other\n'):
            source = SOURCE + suffix
            with self.subTest(suffix=suffix):
                self.assertIn('G7.QCODES_PARAMETER_SOURCE', self.check(source, selector='power', source_ref='native.py:5', factory='native.py:7'))

    def test_explicit_dynamic_member_protocols_and_class_storage_are_refused(self):
        base = 'from qcodes.parameters import Parameter\nclass Native:\n    def __init__(self):\n        self.power = Parameter(name="power", get_cmd="P?", set_cmd="P {}")\n'
        statements = ('self.__setattr__("power", other)', 'self.__delattr__("power")',
                      'self.__getattribute__("power").get = other',
                      'super().__getattribute__("power").get = other',
                      'getattr(super(), "__getattribute__")("power").get = other',
                      'getter = getattr', 'getattr(self.power, "get")()',
                      'getattr(self.other, "__class__")', 'setattr(self.other, name, value)',
                      '(lambda getattr: getattr(self.visa_handle, "baud_rate"))(other)',
                      '(lambda Parameter: Parameter(instrument=self))(other)',
                      'builtins.getattr(super(), "__getattribute__")("power").get = other')
        for statement in statements:
            with self.subTest(statement=statement):
                self.assertIn('G7.QCODES_PARAMETER_SOURCE', self.check(base+'        '+statement+'\n', selector='power', source_ref='native.py:4'))
        for name in ('__getattribute__', '__getattr__', '__setattr__', '__delattr__',
                     '__dict__', '__slots__', '__new__', '__init_subclass__', '__mro_entries__',
                     '__get__', '__set__', '__delete__'):
            with self.subTest(name=name):
                self.assertIn('G7.QCODES_PARAMETER_SOURCE', self.check(base+'    '+name+' = None\n', selector='power', source_ref='native.py:4'))
        shadow = base+'    staticmethod = None\n    @staticmethod\n    def helper(): return 1\n'
        self.assertIn('G7.QCODES_PARAMETER_SOURCE', self.check(shadow, selector='power', source_ref='native.py:4'))
        alias_import = base+'\nfrom builtins import getattr as lookup\n'
        self.assertIn('G7.QCODES_PARAMETER_SOURCE', self.check(alias_import, selector='power', source_ref='native.py:4'))
        # Real ERASynth uses these ordinary disjoint VISA metadata operations.
        positive = base+'        setattr(self.visa_handle, "baud_rate", 115200)\n    DEFAULT = 1\n    @staticmethod\n    def helper(): return 1\n    def bytes(self):\n        return getattr(self.visa_handle, "bytes_in_buffer")\n'
        self.assertEqual(self.check(positive, selector='power', source_ref='native.py:4'), [])

if __name__ == '__main__': unittest.main()
