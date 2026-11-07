#!/usr/bin/env python3
"""Tests for the bounded, read-only source scan (MHS/registry/source_scan.py).

Each test builds a tiny synthetic clone in a temporary directory; nothing is
imported or executed from it.
"""
from __future__ import annotations

import os
import sys
import tempfile
import textwrap
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
REG = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, REG)

import source_scan as S  # noqa: E402


def write(root, rel, text):
    path = os.path.join(root, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(textwrap.dedent(text))


class SourceScanTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = self.tmp.name

    def tearDown(self):
        self.tmp.cleanup()

    def test_entry_class_with_inherited_api_and_export(self):
        write(self.root, "src/bath/__init__.py", "from .device import Bath\n")
        write(self.root, "src/bath/device.py", """
            import serial

            class BaseBath:
                def __init__(self, port):
                    self.port = port
                def write(self, cmd):
                    pass
                def query(self, cmd):
                    pass

            class Bath(BaseBath):
                temperature = member("IN_PV_00")
                setpoint = member("IN_SP_00", "OUT_SP_00")
                def start(self):
                    pass
                def stop(self):
                    pass
            """)
        write(self.root, "tests/test_bath.py", "class TestBath:\n    def test_a(self):\n        pass\n")
        facts = S.scan_repo(self.root, "acme", "bath")
        top = facts["python"]["entry_classes"][0]
        self.assertEqual(top["symbol"], "bath.device:Bath")
        self.assertEqual((top["file"], top["line"]), ("src/bath/device.py", 12))
        self.assertTrue(top["exported"])
        self.assertIn("serial", top["transport"])
        self.assertIn("serial", facts["python"]["imports"])
        self.assertFalse(any(e["symbol"].startswith("tests") for e in facts["python"]["entry_classes"]))

    def test_gym_registrations_including_entry_point_ids(self):
        write(self.root, "envs/__init__.py", """
            import gymnasium
            gymnasium.register(id="Widget-v0", entry_point="envs.w:W")
            gymnasium.register(id="Meta/MT1", entry_point=lambda: None)
            gymnasium.register(id=f"Family/{name}", entry_point="envs.w:W")
            register_env("PickCube-v1", max_episode_steps=50)
            """)
        ids = S.scan_repo(self.root)["python"]["gym_ids"]
        self.assertEqual(ids, sorted(["Family/{}", "Meta/MT1", "PickCube-v1", "Widget-v0"]))

    def test_python2_files_contribute_regex_imports_only(self):
        write(self.root, "scope.py", "import visa\nprint 'hello'\n")
        py = S.scan_repo(self.root)["python"]
        self.assertEqual((py["parsed"], py["failed"]), (0, 1))
        self.assertIn("visa", py["imports_unparsed"])
        self.assertEqual(py["entry_classes"], [])

    def test_vendored_code_is_not_scanned_as_the_repo(self):
        write(self.root, "third_party/robosuite/x.py", "import omni\n")
        write(self.root, "pkg/m.py", "import mujoco\n")
        py = S.scan_repo(self.root)["python"]
        self.assertIn("mujoco", py["imports"])
        self.assertNotIn("omni", py["imports"])

    def test_markers(self):
        write(self.root, "ros_pkg/package.xml", "<package/>\n")
        write(self.root, "models/arm.xml", "<mujoco model='arm'></mujoco>\n")
        write(self.root, "models/other.xml", "<robot/>\n")
        write(self.root, "pyproject.toml", "[project]\nname='x'\n")
        markers = S.scan_repo(self.root)["markers"]
        self.assertEqual((markers["package_xml"], markers["mjcf"]), (1, 1))
        self.assertEqual(markers["root_build_files"], ["pyproject.toml"])

    def test_readme_lure_and_curated_list_facts(self):
        write(self.root, "README.md", """
            # Tool 2026 Setup Guide
            [![Download](https://x/badge.svg)](https://lure.github.io/tool/)
            Get the cracked full release with a keygen.
            """)
        readme = S.scan_repo(self.root, "lure", "tool")["readme"]
        self.assertEqual(readme["download_cta"], ["https://lure.github.io/tool/"])
        self.assertIn("keygen", readme["lure_words"])
        self.assertEqual(readme["heading"], "Tool 2026 Setup Guide")
        write(self.root, "README.md", "# Awesome arms\nA curated list of robot arm SDKs.\n")
        self.assertTrue(S.scan_repo(self.root)["readme"]["curated_list"])

    def test_vendor_download_and_release_links_are_not_lures(self):
        write(self.root, "README.md", """
            [Download](https://github.com/acme/tool/releases/latest)
            [Download the vendor software](https://assets.vendor.com/Software_v3.zip)
            """)
        self.assertEqual(S.scan_repo(self.root, "acme", "tool")["readme"]["download_cta"], [])

    def test_counts_and_deterministic_output(self):
        write(self.root, "a.py", "x = 1\n")
        write(self.root, "b.cpp", "int main(){}\n")
        write(self.root, "setup.exe", "MZ")
        first = S.scan_repo(self.root)
        counts = first["counts"]
        self.assertEqual((counts["python"], counts["code"], counts["executables"]), (1, 1, 1))
        self.assertEqual(first, S.scan_repo(self.root))
        self.assertEqual(first["tree"], sorted(first["tree"]))


    def test_card_facts_licence_install_mocks_and_limits(self):
        write(self.root, "LICENSE", "MIT License\n\nPermission is hereby granted, free of charge, to any person "
                                    "obtaining a copy\n")
        write(self.root, "pyproject.toml", """
            [build-system]
            requires = ["setuptools"]
            [project]
            name = "bath"
            requires-python = ">=3.9"
            license = "MIT"
            [project.scripts]
            bath = "bath.cli:main"
            """)
        write(self.root, "bath/__init__.py", "from .device import Bath\n")
        write(self.root, "bath/device.py", """
            MAX_TEMP = 150.0
            TEMP_RANGE = (-20, 150)
            TIMEOUT = 5

            class Bath:
                SPEED_MAX = 3
                def get_temperature(self):
                    pass
                def set_temperature(self, value):
                    pass
                def stop(self):
                    pass
            """)
        write(self.root, "bath/sim.py", "class SimBath:\n    def get_temperature(self):\n        return 20\n")
        write(self.root, "bath/emulator.py", "def reply(cmd):\n    return '20.0'\n")
        write(self.root, "tests/test_bath.py", "class FakeSerial:\n    pass\n")
        write(self.root, "sim/inst.yaml", "spec: '1.0'\ndevices:\n  bath:\n    dialogues:\n      - q: '*IDN?'\n")
        facts = S.scan_repo(self.root, "acme", "bath")
        self.assertEqual(facts["license"], {"files": ["LICENSE"], "spdx": "MIT", "file": "LICENSE"})
        self.assertEqual(facts["install"]["python_requires"], ">=3.9")
        self.assertEqual(facts["install"]["console_scripts"], ["bath=bath.cli:main"])
        self.assertTrue(facts["install"]["pyproject_buildable"])
        self.assertEqual(facts["install"]["declared_license"], ["MIT"])
        mocks = {(m["kind"], m["file"]) for m in facts["mocks"]}
        self.assertIn(("class", "bath/sim.py"), mocks)
        self.assertIn(("module", "bath/emulator.py"), mocks)    # a simulator module without a mock class
        self.assertIn(("class", "tests/test_bath.py"), mocks)
        self.assertIn(("pyvisa-sim", "sim/inst.yaml"), mocks)
        names = {h["name"]: h for h in facts["limit_hints"]}
        self.assertEqual(names["MAX_TEMP"]["value"], "150.0")
        self.assertEqual(names["TEMP_RANGE"]["value"], "[-20, 150]")
        self.assertIn("SPEED_MAX", names)                     # class-level constants count
        self.assertNotIn("TIMEOUT", names)
        self.assertEqual(facts["markers"]["test_dirs"], ["tests"])
        bath = [c for c in facts["python"]["entry_classes"] if c["symbol"] == "bath.device:Bath"]
        self.assertTrue(bath and set(bath[0]["api_methods"]) >= {"get_temperature", "set_temperature", "stop"})
        self.assertIn("Bath", facts["python"]["exported_names"])

    def test_gym_registration_records_the_class_location(self):
        write(self.root, "toy/__init__.py", """
            from gymnasium.envs.registration import register
            register(id="Toy-v1", entry_point="toy.env:ToyEnv")
            register(id="Ext-v0", entry_point="other.pkg:Missing")
            """)
        write(self.root, "toy/env.py", "import gymnasium\n\n\nclass ToyEnv(gymnasium.Env):\n    def step(self, a):\n"
                                       "        pass\n    def reset(self):\n        pass\n")
        entries = {e["id"]: e for e in S.scan_repo(self.root)["python"]["gym_entries"]}
        self.assertEqual((entries["Toy-v1"]["file"], entries["Toy-v1"]["line"]), ("toy/__init__.py", 3))
        self.assertEqual((entries["Toy-v1"]["class_file"], entries["Toy-v1"]["class_line"]), ("toy/env.py", 4))
        self.assertNotIn("class_file", entries["Ext-v0"])     # defined outside the repo

    def test_monorepo_src_layout_reexported_gym_class_and_external_entry(self):
        # a monorepo distribution: python/<dist>/src/<package>/...
        write(self.root, "python/acme-client/src/acme/client/robot.py", """
            import grpc
            class Robot:
                def connect(self): pass
                def power_on(self): pass
                def power_off(self): pass
                def stop(self): pass
            """)
        write(self.root, "toy/__init__.py", """
            from gymnasium.envs.registration import register
            register(id="Toy-v1", entry_point="toy.envs:ToyEnv")
            register(id="Ext-v0", entry_point="isaaclab.envs:ManagerBasedRLEnv")
            """)
        write(self.root, "toy/envs/__init__.py", "from .toy import ToyEnv\n")
        write(self.root, "toy/envs/toy.py", """
            import gymnasium
            class ToyEnv(gymnasium.Env):
                def step(self, a): pass
                def reset(self): pass
            """)
        facts = S.scan_repo(self.root, "acme", "toy")
        symbols = [c["symbol"] for c in facts["python"]["entry_classes"]]
        self.assertIn("acme.client.robot:Robot", symbols)
        regs = {r["entry_point"]: r for r in facts["python"]["gym_entries"]}
        toy = regs["toy.envs:ToyEnv"]
        self.assertEqual((toy["class_file"], toy["class_line"], toy["class_resolved"], toy["module_in_repo"]),
                         ("toy/envs/toy.py", 3, "reexport", True))
        ext = regs["isaaclab.envs:ManagerBasedRLEnv"]
        self.assertFalse(ext["module_in_repo"])
        self.assertNotIn("class_file", ext)

    def test_microcontroller_and_generated_classes_are_flagged(self):
        write(self.root, "board/lib/as7341.py", """
            from time import sleep_ms
            class AS7341:
                def enable(self): pass
                def disable(self): pass
                def get_channel_data(self): pass
                def set_gain(self, g): pass
            """)
        write(self.root, "pkg/anim.py", """
            import flatbuffers
            class AnimClip:
                def get_name(self): pass
                def get_frames(self): pass
                def get_length(self): pass
                def get_keyframes(self): pass
                def set_speed(self, s): pass
            """)
        write(self.root, "pkg/device.py", """
            import serial
            class Device:
                def open(self): pass
                def get_value(self): pass
                def set_value(self, v): pass
            """)
        facts = S.scan_repo(self.root, "acme", "demo")
        by = {c["symbol"]: c for c in facts["python"]["entry_classes"]}
        self.assertTrue(by["board.lib.as7341:AS7341"]["microcontroller"])
        self.assertTrue(by["pkg.anim:AnimClip"]["generated"])
        self.assertFalse(by["pkg.device:Device"]["microcontroller"] or by["pkg.device:Device"]["generated"])


if __name__ == "__main__":
    unittest.main()


ROBOT_XML = """<mujoco model="arm">
  <worldbody><body name="link"><joint name="j1"/><geom size="0.1"/></body></worldbody>
  <actuator><position joint="j1"/></actuator>
</mujoco>
"""
OBJECT_XML = """<mujoco model="mug">
  <worldbody><body name="mug"><freejoint/><geom size="0.05"/></body></worldbody>
</mujoco>
"""


class PackageFactsTests(unittest.TestCase):
    """Facts added for the rule-9 markers and the card fields (scan version 9)."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = self.tmp.name

    def tearDown(self):
        self.tmp.cleanup()

    def test_registrations_in_examples_tests_and_docs_are_not_the_package(self):
        write(self.root, "pkg/__init__.py", 'import gymnasium\ngymnasium.register(id="Pkg-v0", entry_point="pkg.e:E")\n')
        write(self.root, "examples/custom_env/env.py", 'import gymnasium\ngymnasium.register(id="Demo-v1", entry_point="env:D")\n')
        write(self.root, "tests/conftest.py", 'import gymnasium\ngymnasium.register(id=f"{name}-v0", entry_point="x:Y")\n')
        py = S.scan_repo(self.root, "acme", "pkg")["python"]
        self.assertEqual(py["gym_ids"], ["Pkg-v0"])
        self.assertEqual(py["gym_ids_aux"], ["Demo-v1", "{}-v0"])
        self.assertEqual([e["id"] for e in py["gym_entries"]], ["Pkg-v0"])

    def test_class_object_vector_entry_point_and_decorator_registrations(self):
        write(self.root, "crazy/envs/__init__.py", """
            from gymnasium import register
            from crazy.envs.reach import ReachEnv
            from . import land
            register(id="Reach-v0", vector_entry_point=ReachEnv)
            register(id="Land-v0", entry_point=land.LandEnv)
            register(id="Slide{}-v1".format("Dense"), entry_point="crazy.envs.reach:ReachEnv")
            """)
        write(self.root, "crazy/envs/reach.py", "class ReachEnv:\n    def step(self): pass\n    def reset(self): pass\n")
        write(self.root, "crazy/envs/land.py", "class LandEnv:\n    def step(self): pass\n    def reset(self): pass\n")
        write(self.root, "tasks/push.py", """
            from mani_skill.utils.registration import register_env

            @register_env("PushCube-v1", max_episode_steps=50)
            class PushCubeEnv(BaseEnv):
                def step(self, a): pass
            """)
        regs = {r["id"]: r for r in S.scan_repo(self.root, "acme", "crazy")["python"]["gym_entries"]}
        self.assertEqual(regs["Reach-v0"]["entry_point"], "crazy.envs.reach:ReachEnv")
        self.assertEqual(regs["Land-v0"]["entry_point"], "crazy.envs.land:LandEnv")
        self.assertEqual((regs["Land-v0"]["class_file"], regs["Land-v0"]["class_line"]), ("crazy/envs/land.py", 1))
        self.assertTrue(regs["Slide{}-v1"]["template"])
        self.assertFalse(regs["Reach-v0"]["template"])
        push = regs["PushCube-v1"]
        self.assertEqual((push["entry_point"], push["form"], push["line"]), ("tasks.push:PushCubeEnv", "decorator", 5))

    def test_mjcf_main_models_skip_objects_fragments_templates_and_examples(self):
        write(self.root, "pkg/assets/scene.xml", '<mujoco model="scene">\n  <include file="arm.xml"/>\n'
                                                 '  <worldbody><light/></worldbody>\n</mujoco>\n')
        write(self.root, "pkg/assets/arm.xml", ROBOT_XML)
        write(self.root, "pkg/assets/objects/mug.xml", OBJECT_XML)
        write(self.root, "pkg/assets/actuators.xml", '<mujoco>\n  <actuator><motor joint="j1"/></actuator>\n</mujoco>\n')
        write(self.root, "pkg/assets/template.xml", '<mujoco model="t">\n  <include file="{robot_filename}"/>\n'
                                                    '  <worldbody/>\n</mujoco>\n')
        write(self.root, "examples/panda/scene.xml", ROBOT_XML)
        write(self.root, "pkg/assets/grippers/hand.xml", ROBOT_XML)     # a component another model includes
        write(self.root, "pkg/assets/vx300s(not_support_now)/scene.xml", ROBOT_XML)
        markers = S.scan_repo(self.root, "acme", "arm")["markers"]
        self.assertEqual(markers["mjcf_main"], [{"file": "pkg/assets/scene.xml", "line": 1, "kind": "scene"},
                                                {"file": "pkg/assets/arm.xml", "line": 1, "kind": "robot"}])
        self.assertEqual((markers["mjcf"], markers["mjcf_aux"]), (8, 1))
        self.assertNotIn("examples/panda/scene.xml", markers["mjcf_paths"])
        objects_only = tempfile.TemporaryDirectory()
        try:
            write(objects_only.name, "models/mug/model.xml", OBJECT_XML)
            self.assertEqual(S.scan_repo(objects_only.name, "acme", "objects")["markers"]["mjcf_main"], [])
        finally:
            objects_only.cleanup()

    def test_actuator_includes_and_includes_that_climb_out_of_the_clone(self):
        # mujoco_panda: <actuator><include file="panda/actuators/torque.xml"/></actuator> with bare <motor/> elements
        write(self.root, "models/panda.xml", '<mujoco model="panda">\n  <include file="panda/arm.xml"/>\n'
                                             '  <worldbody><body/></worldbody>\n'
                                             '  <actuator><include file="panda/actuators/torque.xml"/></actuator>\n</mujoco>\n')
        write(self.root, "models/panda/arm.xml", '<mujoco>\n  <body name="link"><joint name="j1"/></body>\n</mujoco>\n')
        write(self.root, "models/panda/actuators/torque.xml", '<mujoco>\n  <motor joint="j1"/>\n</mujoco>\n')
        # unitree_sim: a1.xml includes ../unitree_sim/basic_scene.xml from the clone's own root
        write(self.root, "a1.xml", '<mujoco model="a1">\n  <include file="../quads/basic_scene.xml"/>\n'
                                   '  <worldbody><body><joint name="hip"/></body></worldbody>\n'
                                   '  <actuator><motor joint="hip"/></actuator>\n</mujoco>\n')
        write(self.root, "basic_scene.xml", '<mujoco model="basic">\n  <worldbody><light/></worldbody>\n</mujoco>\n')
        write(self.root, "_vendor_parts/2f85.xml", ROBOT_XML)     # a private part sorts after the repo's models
        main = S.scan_repo(self.root, "acme", "quads")["markers"]["mjcf_main"]
        self.assertEqual([m["file"] for m in main], ["a1.xml", "models/panda.xml", "_vendor_parts/2f85.xml"])

    def test_package_roots_from_poetry_from_give_importable_module_paths(self):
        write(self.root, "pyproject.toml", '[tool.poetry]\nname = "nidaq"\n'
                                           'packages = [{ include = "nidaq", from = "generated" }]\n')
        write(self.root, "generated/nidaq/task.py", """
            import ctypes
            class Task:
                def start(self): pass
                def stop(self): pass
                def read(self): pass
                def write(self, v): pass
            """)
        facts = S.scan_repo(self.root, "acme", "nidaq")
        self.assertEqual(facts["install"]["package_roots"], ["generated"])
        self.assertEqual(facts["python"]["entry_classes"][0]["symbol"], "nidaq.task:Task")

    def test_core_imports_leave_out_guarded_and_test_or_benchmark_imports(self):
        write(self.root, "lockin/filter.py", "try:\n    import cupy\nexcept ImportError:\n    cupy = None\n"
                                             "import numpy\nif USE_CUDA:\n    import sigpy\n")
        write(self.root, "timeit/cuda_bench.py", "import cupy\n")
        write(self.root, "minimal_test/cuda.py", "import pycuda\n")
        py = S.scan_repo(self.root, "acme", "lockin")["python"]
        self.assertTrue({"cupy", "sigpy", "pycuda", "numpy"} <= set(py["imports"]))
        self.assertEqual(py["imports_core"], ["numpy"])

    def test_composed_members_and_environment_classes(self):
        write(self.root, "dobot/robot.py", """
            import socket
            from .motion import Motion
            class Robot:
                def __init__(self, ip):
                    self.motion = Motion(self)
                def connect(self): pass
                def enable_robot(self): pass
                def get_status(self): pass
                def stop(self): pass
            """)
        write(self.root, "dobot/motion.py", "class Motion:\n    def MovJ(self, pose): pass\n    def MovL(self, pose): pass\n")
        write(self.root, "libero/envs/base.py", """
            from robosuite.environments.manipulation.single_arm_env import SingleArmEnv
            class BaseDomain(SingleArmEnv):
                pass
            @register_problem
            class KitchenTask(BaseDomain):
                pass
            class SubprocVectorEnv(BaseDomain):
                pass
            """)
        write(self.root, "README.md", "```python\nfrom libero.envs import OffScreenRenderEnv\n```\n")
        write(self.root, "libero/envs/wrapper.py", "class OffScreenRenderEnv(KitchenTask):\n    pass\n")
        # a plugin registry's decorator registers a processing step, not an environment
        write(self.root, "lerobot/processor.py", """
            @ProcessorStepRegistry.register(name="add_batch_dimension")
            class AddBatchDimensionStep:
                def __call__(self, x): pass
            """)
        facts = S.scan_repo(self.root, "acme", "dobot")
        robot = next(c for c in facts["python"]["entry_classes"] if c["symbol"] == "dobot.robot:Robot")
        self.assertEqual(robot["composes"], [{"attr": "motion", "class": "Motion"}])
        self.assertEqual(robot["composed_methods"], ["motion.MovJ", "motion.MovL"])
        envs = [e["symbol"] for e in facts["python"]["env_entries"]]
        self.assertEqual(envs[0], "libero.envs.wrapper:OffScreenRenderEnv")
        self.assertIn("libero.envs.base:KitchenTask", envs)
        self.assertNotIn("libero.envs.base:SubprocVectorEnv", envs)
        self.assertNotIn("lerobot.processor:AddBatchDimensionStep", envs)

    def test_readme_artifact_downloads(self):
        facts = S.readme_facts("Run `python -m robocasa.scripts.download_kitchen_assets` first.\n"
                               "Caution: Assets to be downloaded are around 10GB.\nThen `git lfs pull`.\n")
        self.assertEqual(facts["artifact_downloads"], ["Assets to be downloaded are around 10GB", "download_kitchen_assets",
                                                       "git lfs pull"])
        self.assertEqual(S.readme_facts("pip install mylib\n")["artifact_downloads"], [])
