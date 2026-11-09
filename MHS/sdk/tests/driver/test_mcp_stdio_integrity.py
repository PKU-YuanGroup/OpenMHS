"""Owned stdio is finite controlled authority; native and G3 remain closed."""
import copy
import importlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from mhs.adapter import load_driver, LoadError
from mhs.bridge.mcp_stdio import OwnedStdioTransport, StdioBudget
from mhs.bridge.mcp_client import native_unavailable
from tests.driver.test_mcp_client import FIXTURE,fixture
from tests.driver import test_qcodes_integrity as prior_integrity


class StdioIntegrityTests(unittest.TestCase):
    def test_fixed_executable_concrete_detached_policy_and_source_digest(self):
        with tempfile.TemporaryDirectory() as directory:
            limits=StdioBudget(frame_bytes=1024,aggregate_bytes=2048)
            peer=OwnedStdioTransport(directory,budget=limits)
            self.addCleanup(peer.close)
            object.__setattr__(limits,'frame_bytes',999999999)
            self.assertEqual(peer._budget.frame_bytes,1024)
            with self.assertRaises(ValueError):OwnedStdioTransport(directory,budget=limits)
            with self.assertRaises(TypeError):OwnedStdioTransport(directory,command=['anything'])
            with self.assertRaises(TypeError):OwnedStdioTransport(directory,budget={'frame_bytes':10})
            with self.assertRaises(TypeError):type('ArbitraryPeer',(OwnedStdioTransport,),{})
            from mhs.bridge import mcp_stdio
            with patch.object(mcp_stdio,'_PEER_SHA256','0'*64),patch.object(subprocess,'Popen',side_effect=AssertionError('must not spawn')) as spawn:
                with self.assertRaises(Exception):peer.exchange({'jsonrpc':'2.0','id':'hash','method':'tools/list','params':{}},lane='normal',timeout_ms=1000)
                spawn.assert_not_called()
            self.assertTrue(peer.wait_retired(1))
        for field in ('frame_bytes','aggregate_bytes','outgoing_bytes','handshake_bytes','control_bytes','handshake_ms','write_ms','grace_ms','terminate_ms','kill_ms','ledger_ids','stderr_bytes','control_rate','controls_per_request'):
            for value in (0,True,10**10):
                with self.subTest(field=field,value=value),self.assertRaises(ValueError):StdioBudget(**{field:value})

    def test_native_refusal_and_stock_unsigned_admission_precede_child_import(self):
        native=importlib.import_module('.native',fixture.__package__)
        tracked=lambda:{name for name in sys.modules if name.split('.')[0] in {'mcp','rigol_dho_mcp','pyvisa'}}
        before=tracked()
        with tempfile.TemporaryDirectory() as directory:
            peer=OwnedStdioTransport(directory)
            self.addCleanup(peer.close)
            with patch.object(subprocess,'Popen',side_effect=AssertionError('no native child')) as spawn:
                for call in (native_unavailable,native.connect,lambda:fixture.Driver(backend='hardware',native=peer),lambda:load_driver(FIXTURE,backend='hardware',allow_hardware=True,native=peer,state_dir=Path(directory)/'hardware-state')):
                    with self.assertRaisesRegex(RuntimeError,'native admission blocked'):call()
                spawn.assert_not_called()
            self.assertIsNone(peer.status()['pid']);self.assertEqual(tracked(),before)
            package=Path(directory)/'unsigned';shutil.copytree(FIXTURE,package)
            path=package/'driver.py';source=path.read_text();needle="mode,risk='hardware','R0'"
            self.assertEqual(source.count(needle),1);path.write_text(source.replace(needle,"mode,risk='hardware','R2'"))
            with patch.object(subprocess,'Popen',side_effect=AssertionError('signature refusal must precede spawn')) as spawn:
                with self.assertRaises(LoadError) as caught:
                    load_driver(package,backend='hardware',allow_hardware=True,native=peer,state_dir=Path(directory)/'state')
                self.assertEqual(caught.exception.reason,'review_required');spawn.assert_not_called()
            self.assertIsNone(peer.status()['pid']);self.assertEqual(tracked(),before)

    def test_computed_module_function_class_and_policy_mutations_fail_stock_g3(self):
        runner=prior_integrity.QcodesGateIntegrityTests()
        prefix='from importlib import import_module\nmodule=import_module(".".join(["mhs","bridge","mcp_stdio"]))\n'
        for statement in ("module._PEER_SHA256='0'*64", "module._EXECUTABLE='/untrusted/program'",
                          'module._pairs=lambda pairs: dict(pairs)',
                          'module.OwnedStdioTransport.ownership_guard=lambda self: None',
                          'module.StdioBudget.__post_init__=lambda self: None'):
            result=runner.stock(prefix+statement+'\n')
            self.assertEqual(result['static'],[],result)
            self.assertEqual(result['gate']['status'],'fail',result)
            self.assertTrue(any(f['code']=='G3.GATE_TAMPERED' for f in result['gate']['findings']),result)
            self.assertEqual(result['native_imports'],[])
        self.assertEqual(runner.stock('')['gate']['status'],'pass')

    def test_complete_unmodified_fixture_stock_cli_g1_to_g9(self):
        sdk=Path(__file__).resolve().parents[2];project=sdk.parents[1]
        env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',PYTHONOPTIMIZE='0',PYTHONPATH=str(sdk/'src'))
        command=[sys.executable,'-m','mhs.driver','check',str(FIXTURE),'--root',str(project),'--backend','fake','--json','--no-report']
        before={str(p.relative_to(FIXTURE)):p.read_bytes() for p in FIXTURE.rglob('*') if p.is_file()}
        run=subprocess.run(command,cwd=project,env=env,capture_output=True,text=True,timeout=180)
        self.assertEqual(run.returncode,0,run.stdout+run.stderr)
        report=json.loads(run.stdout)
        self.assertEqual([g['id'] for g in report['gates']],['G'+str(n) for n in range(1,10)])
        self.assertTrue(report['passed'],report)
        self.assertTrue(all(g['status'] in ('pass','warn') for g in report['gates']),report)
        self.assertEqual({f['code'] for g in report['gates'] for f in g['findings'] if f['severity']=='warning'},
                         {'G2.SYNTHETIC','G7.MCP_NATIVE_UNRESOLVED'})
        self.assertEqual(before,{str(p.relative_to(FIXTURE)):p.read_bytes() for p in FIXTURE.rglob('*') if p.is_file()})


if __name__=='__main__':unittest.main()
