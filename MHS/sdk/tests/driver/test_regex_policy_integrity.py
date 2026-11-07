"""Compiled source/selector policies cannot change invisibly during stock G3."""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import unittest

SDK = Path(__file__).resolve().parents[2]

CHILD = r'''from pathlib import Path
import importlib,json,re,shutil,sys,tempfile
from mhs.driver import Field
from mhs.driver.check import run_check,static_findings
sdk=Path(sys.argv[1]); target=importlib.import_module(sys.argv[2]); key=sys.argv[3]
if key == "_INTEGRITY_BYTES_POLICY":
    target._INTEGRITY_BYTES_POLICY = re.compile(b"ab+")
old=getattr(target,key)
def admissible():
    try:
        if hasattr(target,"parameter_specs"):
            target.parameter_specs({"value":{"parameter":"_hidden","get":True,"set":True,
                "timeout_ms":1,"source_ref":"native.py:1"}},{"value":Field("number",writable=True)})
        elif hasattr(target,"signal_specs"):
            target.signal_specs({"value":{"signal":"_hidden","get":True,"set":True,
                "timeout_ms":1,"source_ref":"native.py:1","get_kwargs":{},"profile":"classic_soft_v1"}},
                {"value":Field("number",writable=True)})
        else:return None
        return True
    except Exception:return False
before=admissible()
with tempfile.TemporaryDirectory() as temp:
    package=Path(temp)/"thermostat";shutil.copytree(sdk/"examples/thermostat",package)
    driver=package/"driver.py";driver.write_text(driver.read_text()+"\n"+sys.argv[4])
    static=static_findings(package);report=run_check(package,gates=["G3"],write_report=False)
    gate=next(g for g in report["gates"] if g["id"]=="G3")
    native_imports=sorted(name for name in sys.modules if name.split(".")[0] in
                         {"qcodes","qcodes_contrib_drivers","pyvisa","visa","ophyd"})
    print(json.dumps({"static":static,"gate":gate,"private_selector_before":before,
        "private_selector_after":admissible(),"object_replaced":getattr(target,key) is not old,
        "pattern_text_equal":getattr(target,key).pattern == old.pattern,
        "native_imports":native_imports}))
'''


LIFETIME_CHILD = r'''from pathlib import Path
import importlib,json,re,shutil,sys,tempfile,weakref
from mhs.driver import Field
from mhs.driver.check import run_check,static_findings
sdk=Path(sys.argv[1]); target=importlib.import_module("mhs.driver.qcodes_config")
try: importlib.import_module("mhs.driver.ophyd_config")
except ModuleNotFoundError: pass
# Give this lifetime test an exclusive, equivalent compiled object. Other
# helpers may legitimately share the original through re.compile's cache.
re.purge()
target._PATH=re.compile(target._PATH.pattern,target._PATH.flags)
# A later import must not acquire the test-owned object from the regex cache.
re.purge()
original_ref=weakref.ref(target._PATH)
def admissible():
    try:
        target.parameter_specs({"value":{"parameter":"_hidden","get":True,"set":True,
            "timeout_ms":1,"source_ref":"native.py:1"}},{"value":Field("number",writable=True)})
        return True
    except Exception:return False
before=admissible()
with tempfile.TemporaryDirectory() as temp:
    package=Path(temp)/"thermostat";shutil.copytree(sdk/"examples/thermostat",package)
    driver=package/"driver.py";driver.write_text(driver.read_text()+"\n"+sys.argv[2])
    static=static_findings(package);report=run_check(package,gates=["G3"],write_report=False)
    gate=next(g for g in report["gates"] if g["id"]=="G3")
    observation=json.loads((package/"regex-lifetime-observation.json").read_text())
    print(json.dumps({"static":static,"gate":gate,"observation":observation,
        "private_selector_before":before,"private_selector_after":admissible(),
        "original_alive_after_gate":original_ref() is not None,
        "native_imports":sorted(name for name in sys.modules if name.split(".")[0] in
            {"qcodes","qcodes_contrib_drivers","pyvisa","visa","ophyd"})}))
'''

LIFETIME_MUTATION = '''import json,re,weakref
from importlib import import_module
from pathlib import Path
module=import_module('.'.join(['mhs','driver','qcodes_config']))
raw,flags,previous_id=module._PATH.pattern,module._PATH.flags,id(module._PATH)
reference=weakref.ref(module._PATH)
owners=[]
for family in ('qcodes','ophyd'):
    try: owner=import_module('.'.join(['mhs','driver',family+'_config']))
    except ModuleNotFoundError: continue
    if id(owner._PATH)==previous_id: owners.append(owner)
alternate=raw.replace('A-Z','A-_')
class PolicyText(str):
    def __getitem__(self,index): return alternate[index]
re.purge()
for owner in owners: owner._PATH=None
snapshot_kept_alive=reference() is not None
replacement=re.compile(PolicyText(raw),flags)
for owner in owners: owner._PATH=replacement
Path(__file__).with_name('regex-lifetime-observation.json').write_text(json.dumps({
    'snapshot_kept_alive':snapshot_kept_alive,'same_raw_pattern':replacement.pattern==raw,
    'same_flags':replacement.flags==flags,'same_id':id(replacement)==previous_id}))
'''


class RegexPolicyIntegrityTests(unittest.TestCase):
    def stock(self, mutation, *, module="qcodes_config", key="_PATH"):
        source = ("import re\nfrom importlib import import_module\n"
                  "module = import_module('.'.join(['mhs', 'driver', " + repr(module) + "]))\n" + mutation + "\n")
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PYTHONPATH=str(SDK / "src"))
        completed = subprocess.run([sys.executable, "-c", CHILD, str(SDK),
                                    "mhs.driver." + module, key, source], env=env,
                                   capture_output=True, text=True, timeout=30)
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        result = json.loads(completed.stdout.strip().splitlines()[-1])
        self.assertEqual(result["static"], [], result)
        self.assertEqual(result["native_imports"], [])
        return result

    def assert_tampered(self, result, member):
        self.assertEqual(result["gate"]["status"], "fail", result)
        self.assertTrue(any(f["code"] == "G3.GATE_TAMPERED" and member in f["message"]
                            for f in result["gate"]["findings"]), result)

    def test_exact_private_selector_admission_change_is_rejected(self):
        result = self.stock("module._PATH = re.compile('.*')")
        self.assertFalse(result["private_selector_before"])
        self.assertTrue(result["private_selector_after"])
        self.assert_tampered(result, "qcodes_config._PATH")

    def test_reusing_compiled_string_pattern_is_allowed(self):
        result = self.stock("module._PATH = re.compile(module._PATH)")
        self.assertFalse(result["object_replaced"])
        self.assertEqual(result["gate"]["status"], "pass", result)
        self.assertFalse(result["private_selector_before"])
        self.assertFalse(result["private_selector_after"])

    def test_equivalent_new_string_policy_object_is_detected(self):
        result = self.stock("re.purge()\nmodule._PATH = re.compile(module._PATH.pattern, module._PATH.flags)")
        self.assertTrue(result["object_replaced"])
        self.assertFalse(result["private_selector_after"])
        self.assert_tampered(result, "qcodes_config._PATH")

    def test_pattern_flags_change_is_detected(self):
        result = self.stock("module._PATH = re.compile(module._PATH.pattern, module._PATH.flags | re.IGNORECASE)")
        self.assert_tampered(result, "qcodes_config._PATH")

    def test_string_subclass_cannot_forge_previous_policy_fingerprint(self):
        result = self.stock('''original = module._PATH
class str(type(original.pattern)):
    def encode(self, *args, **kwargs): return original.pattern.encode(*args, **kwargs)
    def __len__(self): return len(original.pattern)
module._PATH = re.compile(str('.*'), original.flags)''')
        self.assertFalse(result["private_selector_before"])
        self.assertTrue(result["private_selector_after"])
        self.assert_tampered(result, "qcodes_config._PATH")

    def test_compiled_subclass_behavior_cannot_hide_behind_same_raw_pattern(self):
        result = self.stock('''original = module._PATH
class PolicyText(type(original.pattern)):
    def __getitem__(self, index): return '.*'[index]
module._PATH = re.compile(PolicyText(original.pattern), original.flags)''')
        self.assertTrue(result["pattern_text_equal"])
        self.assertFalse(result["private_selector_before"])
        self.assertTrue(result["private_selector_after"])
        self.assert_tampered(result, "qcodes_config._PATH")

    def test_gate_keeps_replaced_policy_alive_until_checked(self):
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PYTHONPATH=str(SDK / "src"))
        completed = subprocess.run([sys.executable, "-c", LIFETIME_CHILD, str(SDK), LIFETIME_MUTATION],
                                   env=env, capture_output=True, text=True, timeout=30)
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        result = json.loads(completed.stdout.strip().splitlines()[-1])
        self.assertEqual(result["static"], [], result)
        self.assertEqual(result["native_imports"], [])
        self.assertTrue(result["observation"]["snapshot_kept_alive"], result)
        self.assertTrue(result["observation"]["same_raw_pattern"])
        self.assertTrue(result["observation"]["same_flags"])
        self.assertFalse(result["observation"]["same_id"])
        self.assertFalse(result["private_selector_before"])
        self.assertTrue(result["private_selector_after"])
        self.assert_tampered(result, "qcodes_config._PATH")
        self.assertFalse(result["original_alive_after_gate"], result)

    def test_string_to_bytes_pattern_replacement_is_detected(self):
        result = self.stock("module._PATH = re.compile(b'.*')")
        self.assert_tampered(result, "qcodes_config._PATH")

    def test_bytes_policy_content_and_flags_changes_are_detected(self):
        for replacement in ("re.compile(b'a.*')", "re.compile(b'ab+', re.IGNORECASE)"):
            with self.subTest(replacement=replacement):
                result = self.stock("module._INTEGRITY_BYTES_POLICY = " + replacement,
                                    key="_INTEGRITY_BYTES_POLICY")
                self.assert_tampered(result, "qcodes_config._INTEGRITY_BYTES_POLICY")

    def test_reusing_compiled_bytes_pattern_is_allowed(self):
        result = self.stock("module._INTEGRITY_BYTES_POLICY = re.compile(module._INTEGRITY_BYTES_POLICY)",
                            key="_INTEGRITY_BYTES_POLICY")
        self.assertFalse(result["object_replaced"])
        self.assertEqual(result["gate"]["status"], "pass", result)

    def test_equivalent_new_bytes_policy_object_is_detected(self):
        result = self.stock("re.purge()\nmodule._INTEGRITY_BYTES_POLICY = re.compile(b'ab+')",
                            key="_INTEGRITY_BYTES_POLICY")
        self.assertTrue(result["object_replaced"])
        self.assert_tampered(result, "qcodes_config._INTEGRITY_BYTES_POLICY")

    def test_source_reference_regex_replacement_is_detected(self):
        result = self.stock("module.REF_PATTERN = re.compile('.*')", module="upstream", key="REF_PATTERN")
        self.assert_tampered(result, "upstream.REF_PATTERN")
