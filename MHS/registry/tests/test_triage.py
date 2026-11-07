#!/usr/bin/env python3
"""Unit tests for the eleven ordered triage rules (MHS/registry/triage.py).

Every rule is exercised on synthetic facts, so the tests need neither the
corpus nor git.  Run from the workspace root:

    python3 -m unittest discover -s MHS/registry/tests
"""
from __future__ import annotations

import copy
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
REG = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, REG)

import triage as T  # noqa: E402


MAIN_SCENE = {"file": "models/scene.xml", "line": 1, "kind": "scene"}


def scan(python=None, code=0, total=None, imports=(), gym_ids=(), entry=None, package_xml=0, mjcf=0,
         env_classes=0, readme=None, executables=0, notebooks=0, tree=None, unparsed=(), mjcf_main=None,
         mjcf_aux=0, gym_ids_aux=(), entries=None):
    """Minimal source_scan facts."""
    python = 3 if python is None else python
    files = python + code + notebooks + executables + 2
    counts = {"files": files, "python": python, "code": code, "notebooks": notebooks,
              "executables": executables, "installers": 0, "archives": 0, "docs": 2,
              "total": files if total is None else total}
    return {
        "scan_version": 5,
        "tree": list(tree if tree is not None else [f"f{i}.py" for i in range(python)]),
        "truncated": False,
        "counts": counts,
        "readme": readme,
        "python": {"files": python, "parsed": python, "failed": 0, "skipped": 0,
                   "imports": sorted(imports), "imports_unparsed": sorted(unparsed),
                   "gym_ids": list(gym_ids), "gym_id_count": len(gym_ids), "env_classes": env_classes,
                   "gym_ids_aux": list(gym_ids_aux),
                   "classes": 1 if entry else 0,
                   "entry_classes": list(entries) if entries is not None else ([entry] if entry else [])},
        "markers": {"package_xml": package_xml, "package_xml_paths": [], "launch_files": 0, "urdf": 0,
                    "mjcf": mjcf, "mjcf_aux": mjcf_aux, "mjcf_paths": [],
                    "mjcf_main": list(mjcf_main) if mjcf_main is not None else ([MAIN_SCENE] if mjcf > mjcf_aux else []),
                    "unity_project": False, "unreal_project": False,
                    "root_build_files": ["pyproject.toml"], "has_tests": False},
    }


def entry_class(score=14, api=6, transport=("serial",), exported=True, symbol="pkg.dev:Device"):
    return {"symbol": symbol, "file": "pkg/dev.py", "line": 10, "score": score, "bases": [],
            "methods": ["close", "open", "read"], "members": [], "api": api, "exported": exported,
            "async": False, "transport": list(transport)}


def facts(name="gizmo", owner="acme", track="labs", tier="B", category="设备后端", role="设备SDK",
          analyst=None, families=("python-object",), stars=0, git=None, relation="", scan_facts=None,
          **scan_kwargs):
    return T.RepoFacts(
        package_id=f"gh.{owner}/{name}", local_path=f"{track}/{owner}/{name}", track=track, owner=owner,
        repo=name, tier=tier, families=list(families), stars=stars,
        catalog={"category": category, "adapter_role": role, "description_zh": "",
                 "relation_to_other_projects": relation, "limitations": ""},
        analyst=dict(analyst or {}),
        git=dict(git or {"repo_url": f"https://github.com/{owner}/{name}", "commit": None}),
        scan=scan_facts if scan_facts is not None else scan(**scan_kwargs),
    )


def decide(f, *others, overrides=None):
    ctx = T.Context([f, *others])
    return T.decide(f, ctx, overrides)


class RuleOrderTests(unittest.TestCase):
    def test_rules_are_the_eleven_handoff_rules_in_order(self):
        self.assertEqual([n for n, _ in T.RULES], list(range(1, 12)))

    def test_first_match_wins(self):
        # a tutorial (rule 2) that is also a byte-identical fork (rule 5) is decided by rule 2
        tree = [f"src/m{i}.py" for i in range(20)]
        a = facts("ros-course", owner="a", tree=tree, python=20)
        b = facts("ros-course", owner="b", tree=tree, python=20, stars=10)
        d = decide(a, b)
        self.assertEqual((d.rule, d.reason_code), (2, "skip:not-device"))

    def test_rule_11_always_matches(self):
        d = decide(facts(category="", role="", families=()))
        self.assertEqual(d.strategy, "untriaged")
        self.assertTrue(d.reason_code.startswith("untriaged:"))


class Rule1EmptyTests(unittest.TestCase):
    def test_tier_x(self):
        d = decide(facts(tier="X"))
        self.assertEqual((d.rule, d.strategy, d.reason_code), (1, "skip", "skip:empty"))

    def test_empty_clone(self):
        d = decide(facts(python=0, total=0))
        self.assertEqual(d.reason_code, "skip:empty")


class Rule2NotDeviceTests(unittest.TestCase):
    def test_no_source_code(self):
        d = decide(facts(python=0, notebooks=2))
        self.assertEqual((d.rule, d.strategy, d.role), (2, "skip", "docs"))

    def test_analyst_flag_confirmed_by_scan(self):
        d = decide(facts(python=1, analyst={"flags": ["no_source_code"]}))
        self.assertEqual((d.rule, d.reason_code), (2, "skip:not-device"))

    def test_analyst_flag_contradicted_by_code_is_not_a_skip(self):
        f = facts(python=40, analyst={"flags": ["clone_content_gap"]}, imports={"pyvisa"})
        self.assertNotEqual(decide(f).rule, 2)

    def test_awesome_list(self):
        self.assertEqual(decide(facts("awesome-robot-arms", python=1)).reason_code, "skip:not-device")

    def test_curated_list_readme(self):
        f = facts("robot-links", python=2, readme={"curated_list": True})
        self.assertEqual(decide(f).rule, 2)

    def test_course_or_tutorial(self):
        for name in ("mujoco-tutorial", "ros2_tutorials", "robotics-course", "lecture-notes"):
            with self.subTest(name=name):
                self.assertEqual(decide(facts(name, python=30)).rule, 2)


class Rule3QuarantineTests(unittest.TestCase):
    LURE = {"download_cta": ["https://lure.github.io/lure/"], "lure_words": [], "curated_list": False}

    def test_download_lure_with_stub_script(self):
        f = facts("tool-setup-guide", owner="lure", python=1, readme=self.LURE)
        d = decide(f)
        self.assertEqual((d.rule, d.strategy, d.reason_code), (3, "skip", "skip:quarantine"))
        self.assertTrue(d.quarantine)
        self.assertIn("QUARANTINE", d.blocked_on)

    def test_quarantine_is_set_even_when_an_earlier_rule_decides(self):
        f = facts("tool-setup-guide", owner="lure", python=0, readme=self.LURE)
        d = decide(f)
        self.assertEqual(d.rule, 2)
        self.assertTrue(d.quarantine)
        self.assertEqual(d.role, "not-device")

    def test_binary_only_installer(self):
        d = decide(facts(python=0, executables=4))
        self.assertTrue(d.quarantine)

    def test_real_project_with_download_link_is_not_quarantined(self):
        f = facts(python=50, imports={"pyvisa"}, readme=self.LURE)
        self.assertFalse(decide(f).quarantine)


class Rule4PriorArtTests(unittest.TestCase):
    def test_mhs_title(self):
        f = facts("robot-bridge", python=20, readme={"mhs_title": True, "mhs_mentions": 4})
        d = decide(f)
        self.assertEqual((d.rule, d.strategy, d.role, d.reason_code), (4, "reference", "prior-art", "reference:prior-art"))

    def test_mhs_name(self):
        self.assertEqual(decide(facts("open-mhs", python=20, readme={"mhs_mentions": 2})).rule, 4)

    def test_analyst_claim_needs_many_mentions(self):
        f = facts("bench", python=20, analyst={"mhs_claim": "claimed"}, readme={"mhs_mentions": 1})
        self.assertNotEqual(decide(f).rule, 4)


class Rule5DuplicateTests(unittest.TestCase):
    TREE = [f"pkg/m{i}.py" for i in range(30)]

    def test_tree_similarity_picks_the_starred_canonical(self):
        fork = facts("bigym", owner="someone", tree=self.TREE, python=30)
        upstream = facts("bigym", owner="org", tree=self.TREE + ["README.md"], python=30, stars=200)
        d = decide(fork, upstream)
        self.assertEqual((d.rule, d.reason_code, d.variant_of), (5, "skip:duplicate_of", "gh.org/bigym"))
        self.assertIsNone(decide(upstream, fork).variant_of)

    def test_catalogue_fork_note_with_corroborating_tree(self):
        fork = facts("pymeasure", owner="fork", tree=self.TREE[:24], python=24,
                     relation="pymeasure/pymeasure的fork")   # "fork of pymeasure/pymeasure"
        up = facts("pymeasure", owner="pymeasure", tree=self.TREE, python=30)
        self.assertEqual(decide(fork, up).variant_of, "gh.pymeasure/pymeasure")

    def test_fork_note_by_project_name(self):
        fork = facts("qcodes_contrib_drivers", owner="old", tree=self.TREE[:25], python=25,
                     relation="fork of QCoDeS contrib drivers")
        up = facts("qcodes_contrib_drivers", owner="qcodes", tree=self.TREE, python=30)
        other = facts("qcodes", owner="microsoft", tree=["x.py"], python=1)
        self.assertEqual(decide(fork, up, other).variant_of, "gh.qcodes/qcodes_contrib_drivers")

    def test_documented_divergence_is_not_a_duplicate(self):
        fork = facts("imswitch", owner="hard", tree=self.TREE[:16], python=16,
                     relation="README明确为ImSwitch/ImSwitch的hard fork")   # "README says hard fork"
        up = facts("imswitch", owner="imswitch", tree=self.TREE, python=30)
        self.assertNotEqual(decide(fork, up).rule, 5)

    def test_chains_resolve_to_one_root_and_cycles_keep_one_repo(self):
        tree = [f"pkg/m{i}.py" for i in range(30)]
        root = facts("lib", owner="root", tree=tree, python=30, stars=50)
        mid = facts("lib", owner="mid", tree=tree[:26], python=26, relation="fork of root/lib")
        leaf = facts("lib2", owner="leaf", tree=tree[:24], python=24, relation="fork of mid/lib")
        self.assertEqual(decide(leaf, mid, root).variant_of, "gh.root/lib")
        a = facts("x", owner="a", tree=tree, python=30, relation="fork of b/x")
        b = facts("x", owner="b", tree=tree, python=30, relation="fork of a/x")
        kept = [d for d in (decide(a, b), decide(b, a)) if d.variant_of is None]
        self.assertEqual(len(kept), 1)

    def test_same_head_commit(self):
        sha = "a" * 40
        a = facts("x", owner="a", git={"repo_url": "https://github.com/a/x", "commit": sha})
        b = facts("y", owner="b", git={"repo_url": "https://github.com/b/y", "commit": sha}, stars=5)
        self.assertEqual(decide(a, b).variant_of, "gh.b/y")

    def test_different_projects_with_the_same_name_are_kept(self):
        a = facts("drake", owner="factual", tree=["a.go", "b.go"], python=0, code=2)
        b = facts("drake", owner="robotlocomotion", tree=["x/y.cc"], python=0, code=1)
        self.assertNotEqual(decide(a, b).rule, 5)


class Rule6BridgeRuntimeTests(unittest.TestCase):
    def test_protocol_stack(self):
        d = decide(facts("pyvisa", owner="pyvisa", python=40))
        self.assertEqual((d.rule, d.strategy, d.role, d.reason_code, d.family),
                         (6, "bridge-runtime", "transport", "bridge-runtime:scpi", "scpi"))
        self.assertIsNone(d.helper)

    def test_framework_and_engine(self):
        self.assertEqual(decide(facts("lerobot", owner="huggingface")).reason_code, "bridge-runtime:lerobot")
        d = decide(facts("drake", owner="robotlocomotion", track="robots"))
        self.assertEqual((d.strategy, d.reason_code), ("bridge-runtime", "bridge-runtime:engine"))

    def test_every_table_entry_is_a_corpus_repo(self):
        import glob
        import json
        ids = set()
        for path in glob.glob(os.path.join(REG, "repos", "*", "*.json")):
            with open(path, encoding="utf-8") as fh:
                ids.add(json.load(fh)["package_id"])
        self.assertEqual([p for p in T.BRIDGE_RUNTIME if p not in ids], [])

    def test_every_table_entry_names_a_known_family_and_role(self):
        for pid, (family, role) in T.BRIDGE_RUNTIME.items():
            with self.subTest(pid=pid):
                self.assertTrue(family is None or family in T.FAMILIES)
                self.assertIn(role, ("framework", "transport"))


class Rule7HostToolingTests(unittest.TestCase):
    def test_orchestrator_category_is_a_host(self):
        d = decide(facts(category="编排调度", role="外围工具"))   # orchestration / peripheral tool
        self.assertEqual((d.rule, d.strategy, d.role, d.reason_code), (7, "reference", "host", "reference:host"))

    def test_mcp_wrapper_of_a_covered_backend(self):
        f = facts("ros2-mcp-server", category="协议实现/桥接", role="协议桥接", imports={"mcp", "rclpy"})
        self.assertEqual(decide(f).reason_code, "reference:host")

    def test_gui_tooling(self):
        d = decide(facts("qcodes-gui", category="辅助工具", role="外围工具"))   # auxiliary / peripheral tool
        self.assertEqual((d.rule, d.reason_code, d.role), (7, "skip:tooling", "tooling"))

    def test_device_sdk_role_is_never_a_host(self):
        f = facts(category="编排调度", role="设备SDK", imports={"serial"})
        self.assertNotEqual(decide(f).rule, 7)


class Rule8PeripheralTests(unittest.TestCase):
    def test_tier_d(self):
        d = decide(facts(tier="D", category="自动分类/发现", role="物理引擎"))
        self.assertEqual((d.rule, d.strategy, d.reason_code), (8, "skip", "skip:peripheral"))
        self.assertEqual(d.role, "not-device")

    def test_policy_row_without_env_or_device_is_demoted(self):
        f = facts(tier="A", category="策略/算法", role="任务环境", track="robots")   # policy / task env
        self.assertEqual(decide(f).reason_code, "skip:peripheral")

    def test_software_row_with_a_driver_directory_is_not_skipped(self):
        # a hardware abstraction layer the AST cannot read (C++) keeps a control-framework row out of tier D
        tree = [f"src/rl/hal/Drive{i}.cpp" for i in range(5)] + ["CMakeLists.txt"]
        f = facts("rl", category="控制框架", role="控制器", python=0, code=5, tree=tree)   # control framework
        d = decide(f)
        self.assertEqual((d.strategy, d.reason_code), ("untriaged", "untriaged:non_python"))
        self.assertIn("5 source files under src/rl/hal/", T.driver_directory(f))
        tests_only = facts("rl2", category="控制框架", role="控制器", python=0, code=5,
                           tree=[f"tests/hal/t{i}.cpp" for i in range(5)])
        self.assertEqual(decide(tests_only).reason_code, "skip:peripheral")

    def test_software_row_with_a_device_class_is_not_skipped(self):
        stage = entry_class(score=6, api=3, transport=(), symbol="stage:AerotechStage")
        d = decide(facts("zscan", category="控制框架", role="控制器", entry=stage))
        self.assertNotEqual(d.reason_code, "skip:peripheral")
        plain = entry_class(score=6, api=3, transport=(), symbol="solver:Planner")
        self.assertEqual(decide(facts("plan", category="控制框架", role="控制器", entry=plain)).reason_code,
                         "skip:peripheral")

    def test_policy_row_registering_gym_envs_is_kept(self):
        f = facts(tier="A", category="策略/算法", role="任务环境", imports={"gymnasium"}, gym_ids=["Foo-v0"])
        self.assertEqual(decide(f).strategy, "family-config")

    def test_curated_override_beats_tier_d(self):
        f = facts("franka_ros", owner="frankarobotics", tier="D", package_xml=8, analyst={"family": "ros1"})
        override = {f.package_id: {"package_id": f.package_id, "strategy": "family-config", "role": "device-driver",
                                   "family": "ros", "justification": "Official Franka ROS 1 driver."}}
        d = decide(f, overrides=override)
        self.assertEqual((d.rule, d.strategy, d.family), ("override", "family-config", "ros"))
        self.assertIn("rules alone: skip", d.evidence[1])


class Rule9FamilyConfigTests(unittest.TestCase):
    def test_gym_registration_is_a_gymnasium_family_config(self):
        f = facts("gym-widget", category="完整环境", role="任务环境", imports={"gymnasium", "mujoco"},
                  gym_ids=["Widget-v0"], track="robots")
        d = decide(f)
        self.assertEqual((d.rule, d.strategy, d.family, d.helper, d.helper_status, d.role),
                         (9, "family-config", "gymnasium", "GymnasiumDriver", "available", "sim-env"))
        self.assertEqual(d.blocked_on, [])

    def test_gym_env_on_an_external_simulator_has_no_helper(self):
        f = facts("isaac-task", category="完整环境", role="任务环境", imports={"gymnasium", "isaaclab"},
                  gym_ids=["Isaac-Foo-v0"], track="robots")
        self.assertEqual(decide(f).strategy, "untriaged")

    def test_name_alone_never_selects_a_simulator_family(self):
        f = facts("mujoco-gazebo-isaac-sim", category="完整环境", role="任务环境", track="robots")
        self.assertNotEqual(decide(f).strategy, "family-config")

    def test_ros_package_needs_ros_family_evidence(self):
        ros = facts("arm_driver", package_xml=3, analyst={"family": "ros2"}, families=("ros2",), track="robots")
        d = decide(ros)
        self.assertEqual((d.family, d.helper_status, d.blocked_on), ("ros", "available", []))
        self.assertEqual(d.helper, "RosDriver")
        sub = facts("arm_driver", package_xml=1, analyst={"family": "pybullet"}, families=("pybullet",),
                    track="robots", category="设备后端")
        self.assertNotEqual(decide(sub).family, "ros")

    def test_mujoco_models(self):
        f = facts("robot_models", category="模型资产", role="场景资产", python=0, code=0, mjcf=12, track="robots",
                  tier="C")
        d = decide(f)
        self.assertEqual((d.family, d.role), ("mujoco", "twin-candidate"))

    def test_scpi_instrument(self):
        d = decide(facts("keithley-2400", imports={"pyvisa"}))
        self.assertEqual((d.family, d.helper), ("scpi", "ScpiDriver"))

    def test_serial_without_a_strong_class(self):
        d = decide(facts("pump", imports={"serial"}, entry=entry_class(score=6)))
        self.assertEqual((d.family, d.helper), ("serial", "SerialDriver"))

    def test_serial_with_a_strong_class_goes_to_rule_10(self):
        d = decide(facts("pump", imports={"serial"}, entry=entry_class(score=15)))
        self.assertEqual((d.rule, d.strategy), (10, "direct-driver"))

    def test_python2_imports_still_mark_a_family(self):
        d = decide(facts("old-scope", unparsed={"visa"}))
        self.assertEqual(d.family, "scpi")

    def test_post_pilot_framework_is_blocked_on_its_helper(self):
        d = decide(facts("mm-scope", imports={"pymmcore_plus"}))
        self.assertEqual((d.strategy, d.family, d.helper, d.helper_status, d.blocked_on),
                         ("family-config", "pymmcore-plus", None, "blocked", ["helper:pymmcore-plus"]))

    def test_qcodes_framework_uses_its_available_helper(self):
        d = decide(facts("contrib-drivers", imports={"qcodes"}))
        self.assertEqual((d.strategy, d.family, d.helper, d.helper_status, d.blocked_on),
                         ("family-config", "qcodes", "QcodesDriver", "available", []))

    def test_protocol_family_is_never_a_sim_env(self):
        f = facts("blender-sim", category="完整环境", role="任务环境", imports={"pymavlink"}, track="robots")
        self.assertNotEqual(decide(f).strategy, "family-config")


class Rule10DirectDriverTests(unittest.TestCase):
    def test_ast_entry_class_with_device_evidence(self):
        d = decide(facts("laser", imports={"socket"}, entry=entry_class(score=12, transport=("socket",))))
        self.assertEqual((d.rule, d.strategy, d.reason_code, d.family, d.helper),
                         (10, "direct-driver", "PY_SDK_WITH_ENTRY", "python-object", "PythonObjectDriver"))

    def test_weak_entry_is_untriaged(self):
        d = decide(facts("laser", entry=entry_class(score=5, api=2, transport=())))
        self.assertEqual((d.rule, d.reason_code), (11, "untriaged:weak_entry"))

    def test_small_transport_class_of_a_catalogue_device_sdk_is_a_driver(self):
        # a single-file USB or serial driver: score below 9, but the catalogue says device SDK and the class
        # talks to its transport (WP-10 10b spot check: bdhammel/python_newport_controller)
        d = decide(facts("picomotor", imports={"usb"}, entry=entry_class(score=5, api=2, transport=("usb",))))
        self.assertEqual((d.rule, d.strategy, d.reason_code), (10, "direct-driver", "PY_SDK_WITH_ENTRY"))
        self.assertIn("catalogue device SDK", d.evidence[0])
        # the same class without the catalogue device-SDK role stays a recon card
        d = decide(facts("picomotor", role="控制器", imports={"usb"}, entry=entry_class(score=5, api=2, transport=("usb",))))
        self.assertEqual(d.strategy, "untriaged")
        # a ROS package beside the device class is not an external simulator for this path
        d = decide(facts("platform", imports={"usb", "rospy"}, entry=entry_class(score=6, api=4, transport=("usb",))))
        self.assertEqual(d.strategy, "direct-driver")

    def test_strong_class_without_device_evidence_is_not_a_driver(self):
        f = facts("planner", category="协议实现/桥接", role="协议桥接",
                  entry=entry_class(score=15, transport=(), exported=False))
        self.assertNotEqual(decide(f).strategy, "direct-driver")


class InputTests(unittest.TestCase):
    RECORD = {"package_id": "gh.acme/gizmo", "local_path": "labs/acme/gizmo", "tier": "B",
              "families": ["serial"], "stars": 3,
              "x-vendor": {"catalog": {"row": 7, "archived": "false", "category_zh": "设备后端"}}}

    def test_record_profile_lock_and_notes_are_merged(self):
        profile = {"catalog": {"adapter_role": "设备SDK", "relation_to_other_projects": "unknown"},
                   "classification": {"family": "lab-serial", "tier": "A"},
                   "quality": {"flags": ["license_unknown"]}, "mhs": {"claim_class": "unknown"}}
        lock = {"repo_url": "https://github.com/acme/gizmo", "commit": "b" * 40}
        f = T.facts_from_record(self.RECORD, profile, lock, scan(), {7: {"relation_to_other_projects": "fork of x/y",
                                                                         "limitations": ""}})
        self.assertEqual((f.track, f.owner, f.repo, f.tier), ("labs", "acme", "gizmo", "B"))
        self.assertEqual(f.catalog["category"], "设备后端")
        self.assertEqual(f.catalog["relation_to_other_projects"], "fork of x/y")
        self.assertEqual(f.analyst["family"], "lab-serial")
        self.assertEqual(f.git["commit"], "b" * 40)

    def test_clone_audit_is_the_fallback_and_the_cross_check(self):
        audit = {"origin": "https://github.com/acme/gizmo.git", "head": "c" * 40, "valid_head": True,
                 "issues": ["tracked_changes"]}
        f = T.facts_from_record(self.RECORD, None, None, scan(), None, audit)
        self.assertEqual(f.git["repo_url"], "https://github.com/acme/gizmo")
        self.assertEqual(f.git["commit"], "c" * 40)
        moved = T.facts_from_record(self.RECORD, None, {"repo_url": "u", "commit": "d" * 40}, scan(), None, audit)
        self.assertTrue(any("moved since the clone audit" in e for e in decide(moved).evidence))


class Rule11UntriagedTests(unittest.TestCase):
    def test_reasons(self):
        self.assertEqual(decide(facts(python=0, code=12)).reason_code, "untriaged:non_python")
        self.assertEqual(decide(facts()).reason_code, "untriaged:no_entry_class")


class OverrideTests(unittest.TestCase):
    def base(self, **extra):
        item = {"package_id": "gh.acme/gizmo", "strategy": "direct-driver", "role": "device-driver",
                "family": "python-object", "justification": "Curated because the scan cannot see it."}
        item.update(extra)
        return item

    def test_override_wins_and_keeps_rule_quarantine(self):
        f = facts(python=0, readme={"download_cta": ["https://acme.github.io/gizmo"]})
        item = self.base(strategy="skip", role="not-device", family=None)
        d = decide(f, overrides={f.package_id: item})
        self.assertEqual((d.rule, d.strategy), ("override", "skip"))
        self.assertTrue(d.quarantine)

    def test_override_cannot_dispatch_a_quarantined_repo(self):
        f = facts(python=0, readme={"download_cta": ["https://acme.github.io/gizmo"]})
        with self.assertRaises(T.OverrideError):
            decide(f, overrides={f.package_id: self.base()})

    def test_partner_flagship_and_wave_pass_through(self):
        f = facts()
        d = decide(f, overrides={f.package_id: self.base(partner="Tecan", flagship=True, wave=0)})
        self.assertEqual((d.partner, d.flagship, d.wave, d.helper), ("Tecan", True, 0, "PythonObjectDriver"))

    def test_confirmed_entry_symbols_pass_through_but_stay_off_the_decision_record(self):
        f = facts()
        symbols = [{"symbol": "gizmo.core:Gizmo", "file": "gizmo/core.py", "line": 7}]
        d = decide(f, overrides={f.package_id: self.base(reason_code="override:recon", entry_symbols=symbols)})
        self.assertEqual(d.entry_symbols, symbols)
        self.assertNotIn("entry_symbols", d.to_json())

    def test_invalid_overrides_are_refused(self):
        symbol = {"symbol": "gizmo.core:Gizmo", "file": "gizmo/core.py", "line": 7}
        for bad in (self.base(strategy="bogus"), self.base(family=None), self.base(justification="two\nlines"),
                    self.base(quarantine=True), self.base(colour="red"),
                    self.base(strategy="skip", reason_code="skip:duplicate_of", family=None),
                    self.base(strategy="skip", family=None, entry_symbols=[symbol]),
                    self.base(entry_symbols=[]), self.base(entry_symbols=[dict(symbol, line=0)]),
                    self.base(entry_symbols=[dict(symbol, symbol="2220 supplies:KEI2220S")]),
                    self.base(entry_symbols=[dict(symbol, file="Python/../Beam Profiler/TLBC2.py")]),
                    self.base(entry_symbols=[dict(symbol, extra=1)])):
            with self.subTest(bad=bad):
                with self.assertRaises(T.OverrideError):
                    T.check_override(bad)

    def test_unknown_override_targets_are_reported(self):
        self.assertEqual(T.unknown_overrides({"gh.a/b": {}, "gh.c/d": {}}, ["gh.a/b"]), ["gh.c/d"])

    def test_reviewed_classes_and_publication_review_pass_through_but_stay_off_the_decision_record(self):
        f = facts()
        item = self.base(capability_classes=["cap.sensing.image.v1"], publish_review="required")
        T.check_override(item)
        d = decide(f, overrides={f.package_id: item})
        self.assertEqual((d.capability_classes, d.publish_review), (["cap.sensing.image.v1"], "required"))
        self.assertNotIn("capability_classes", d.to_json())
        self.assertNotIn("publish_review", d.to_json())
        omitted = decide(f, overrides={f.package_id: self.base(omit_sim_contract=True)})
        self.assertTrue(omitted.omit_sim_contract)
        self.assertNotIn("omit_sim_contract", omitted.to_json())
        plain = decide(f, overrides={f.package_id: self.base()})
        self.assertEqual((plain.capability_classes, plain.publish_review), ([], None))

    def test_invalid_reviewed_classes_and_publication_reviews_are_refused(self):
        for bad in (self.base(strategy="skip", family=None, capability_classes=["cap.sensing.image.v1"]),
                    self.base(strategy="untriaged", family=None, capability_classes=["cap.sensing.image.v1"]),
                    self.base(capability_classes=[]), self.base(capability_classes="cap.sensing.image.v1"),
                    self.base(capability_classes=["cap.sensing.image.v1", "cap.sensing.image.v1"]),
                    self.base(capability_classes=["sensing.image"]), self.base(capability_classes=["x-cap.acme.a.v1"]),
                    self.base(capability_classes=[f"cap.sensing.c{i}.v1" for i in range(9)]),
                    self.base(publish_review="not_required"), self.base(publish_review=True),
                    self.base(omit_sim_contract=False),
                    self.base(strategy="skip", family=None, omit_sim_contract=True)):
            with self.subTest(bad=bad):
                with self.assertRaises(T.OverrideError):
                    T.check_override(bad)


class DeterminismTests(unittest.TestCase):
    def test_same_facts_same_decisions(self):
        corpus = [facts("a", imports={"pyvisa"}), facts("b", tier="D"), facts("awesome-x", python=1),
                  facts("pyvisa", owner="pyvisa")]
        first = {k: v.to_json() for k, v in T.triage(copy.deepcopy(corpus)).items()}
        second = {k: v.to_json() for k, v in T.triage(list(reversed(copy.deepcopy(corpus)))).items()}
        self.assertEqual(first, second)
        self.assertEqual(list(first), sorted(first))
        summary = T.summarize(T.triage(corpus))
        self.assertEqual(summary["total"], 4)
        self.assertEqual(sum(summary["by_strategy"].values()), 4)

    def test_decision_values_are_schema_enums(self):
        for f in (facts(), facts(tier="X"), facts("pyvisa", owner="pyvisa"), facts(imports={"qcodes"})):
            d = decide(f)
            self.assertIn(d.strategy, T.STRATEGIES)
            self.assertIn(d.role, T.ROLES)
            self.assertRegex(d.reason_code, r"^[A-Za-z][A-Za-z0-9_.:-]*$")
            self.assertLessEqual(len(d.reason_code), 64)


class SimulatorCatalogueTests(unittest.TestCase):
    """A catalogue model or simulation needs a hardware transport before it counts as a device (WP-10 fix)."""

    def test_measurement_model_with_device_backend_category_is_not_a_device(self):
        # scopesim: category device backend, role measurement model, an optical-effect class with no transport
        f = facts("telescope-sim", category="设备后端", role="测量模型",
                  entry=entry_class(score=11, transport=()))
        self.assertIsNone(T.device_evidence(f))
        d = decide(f)
        self.assertNotIn(d.strategy, ("direct-driver", "family-config"))

    def test_task_environment_with_ctypes_is_not_a_device(self):
        # libero-plus: a task environment whose exported class loads a native library through ctypes
        f = facts("bench-plus", category="操作任务环境", role="任务环境",
                  entry=entry_class(score=12, transport=("ctypes",)))
        self.assertIsNone(T.device_evidence(f))
        self.assertEqual(decide(f).role, "sim-env")

    def test_emulator_collection_serving_sockets_is_simulated(self):
        # epics-deviceemulator: an instrument-model collection (direct simulation backend) serving sockets
        f = facts("device-emulators", category="仪器模型集合", role="直接模拟后端",
                  entry=entry_class(score=14, transport=("socket",)))
        self.assertIsNone(T.device_evidence(f))
        self.assertNotEqual(decide(f).role, "twin-candidate")

    def test_hardware_transport_keeps_a_simulation_backend_a_device(self):
        # a programmable power supply over VISA that emulates a PV panel still drives hardware
        f = facts("pv-emulator", category="设备后端", role="测量模型",
                  entry=entry_class(score=14, transport=("pyvisa",)))
        self.assertIn("hardware transport pyvisa", T.device_evidence(f))
        self.assertIn("pyvisa", T.hardware_transport(f))

    def test_plain_device_sdk_keeps_its_evidence(self):
        f = facts("gizmo", category="设备后端", role="设备SDK", entry=entry_class(transport=("socket",)))
        self.assertEqual(T.device_evidence(f), "catalogue category '设备后端'")


class GazeboMarkerTests(unittest.TestCase):
    def test_gym_env_on_gazebo_has_no_helper(self):
        # gymfc: gym registrations whose env starts gzserver on .world files and builds Gazebo plugins
        tree = ["gymfc/envs/fc_env.py", "gymfc/envs/assets/gazebo/worlds/attitude.world",
                "gymfc/envs/assets/gazebo/plugins/FlightControllerPlugin.cpp", "gymfc/__init__.py"]
        f = facts("gymfc", category="完整环境", role="任务环境", tree=tree, imports=("gym",),
                  gym_ids=("gymfc-v1",), env_classes=1)
        self.assertIn("Gazebo world file", T.gazebo_marker(f))
        family, _marker, notes = T.structural_family(f)
        self.assertIsNone(family)
        self.assertTrue(any("Gazebo world file" in n for n in notes))
        self.assertNotEqual(decide(f).strategy, "family-config")

    def test_plugin_directory_alone_is_a_marker(self):
        f = facts("sim", tree=["pkg/env.py", "gazebo_plugins/src/plugin.cc"])
        self.assertIn("Gazebo directory gazebo_plugins/", T.gazebo_marker(f))

    def test_coppeliasim_and_webots_scenes_are_markers(self):
        # gym-ur5: gym envs that talk to a CoppeliaSim scene through its remote API
        f = facts("gym-ur5", tree=["gym_ur5/envs/ur5_env.py", "coppelia_scenes/UR5.ttt"], imports=("gym",),
                  gym_ids=("UR5-v0",), env_classes=1, category="完整环境", role="任务环境")
        self.assertEqual(T.gazebo_marker(f), "CoppeliaSim scene coppelia_scenes/UR5.ttt")
        self.assertIsNone(T.structural_family(f)[0])
        self.assertIn("Webots world", T.gazebo_marker(facts("w", tree=["worlds/a.wbt"])))

    def test_pure_python_gym_env_stays_gymnasium(self):
        f = facts("cartpole-plus", category="完整环境", role="任务环境", tree=["pkg/env.py", "pkg/__init__.py"],
                  imports=("gymnasium",), gym_ids=("CartPolePlus-v0",), env_classes=1)
        self.assertIsNone(T.gazebo_marker(f))
        self.assertEqual(T.structural_family(f)[0], "gymnasium")


class MarkerSourceTests(unittest.TestCase):
    """Rule-9 markers come from the package itself (verification of 10b: examples, assets, GUI hosts, mocks)."""

    def test_example_or_test_registrations_make_no_gymnasium_family(self):
        # openrl, minari: the only registration lives in examples/ or tests/conftest.py (the scan's gym_ids_aux)
        f = facts("rl-framework", category="策略/算法", role="外围工具", imports=("gymnasium",), gym_ids=(),
                  gym_ids_aux=("Custom_Env/IdentityEnv",), env_classes=4, track="robots")
        self.assertNotEqual(T.structural_family(f)[0], "gymnasium")
        self.assertNotEqual(decide(f).strategy, "family-config")
        self.assertTrue(any("only in examples" in n for n in T.structural_family(f)[2]))

    def test_mujoco_needs_a_loadable_scene_or_robot_model(self):
        robots = facts("menagerie", category="模型资产", role="场景资产", python=0, code=0, mjcf=40, track="robots",
                       tier="C", mjcf_main=[{"file": "panda/scene.xml", "line": 1, "kind": "scene"}])
        self.assertEqual((decide(robots).family, decide(robots).role), ("mujoco", "twin-candidate"))
        # object assets only (mujoco_scanned_objects): no family, not a twin
        objects = facts("scanned_objects", category="模型资产", role="场景资产", python=0, code=0, mjcf=300,
                        track="robots", tier="C", mjcf_main=[])
        d = decide(objects)
        self.assertNotEqual(d.strategy, "family-config")
        self.assertEqual(d.role, "not-device")
        # an IK library whose MJCF files are example copies (mink): the copies are no marker
        ik = facts("ik-lib", imports=("mujoco",), mjcf=64, mjcf_aux=64, mjcf_main=[], track="robots",
                   category="控制框架", role="外围工具")
        self.assertEqual(T.mjcf_models(ik), 0)
        self.assertNotEqual(decide(ik).family, "mujoco")

    def test_gui_application_without_a_device_class_takes_no_protocol_family(self):
        gui = facts("pyscope", imports=("pyvisa", "pyside6", "nidaqmx"))
        family, _marker, notes = T.structural_family(gui)
        self.assertIsNone(family)
        self.assertTrue(any("GUI application" in n for n in notes))
        cli = facts("keithley-2400", imports=("pyvisa",))
        self.assertEqual(T.structural_family(cli)[0], "scpi")

    def test_simulators_mocks_and_dummies_are_never_the_entry_class(self):
        sim = entry_class(score=14, symbol="utils.cameras.sim:SimulatedCamera", transport=("pylablib",))
        dummy = entry_class(score=14, symbol="pyzaber.dummy_linear_slides:multiaxis_linear_slides")
        real = entry_class(score=12, symbol="pyzaber.linear_slides:multiaxis_linear_slides")
        self.assertIsNone(facts("cam-control", entries=[sim]).entry())
        self.assertEqual(facts("pyzaber", entries=[dummy, real]).entry()["symbol"],
                         "pyzaber.linear_slides:multiaxis_linear_slides")
        self.assertNotEqual(decide(facts("cam-control", entries=[sim])).strategy, "direct-driver")
        virtual = entry_class(symbol="pycont.controller:VirtualC3000Controller")
        base = entry_class(score=10, symbol="pycont.controller:C3000Controller")
        self.assertTrue(T.is_mock_class(virtual, ["C3000Controller"]))
        self.assertFalse(T.is_mock_class(entry_class(symbol="ni.bench:VirtualBench"), ["VirtualBench"]))
        self.assertEqual(facts("pycont", entries=[virtual, base]).entry()["symbol"], "pycont.controller:C3000Controller")

    def test_unity_based_simulators_are_external_engines(self):
        # co-llm-agents: gym envs over ThreeDWorld (a Unity build) and VirtualHome
        f = facts("co-llm-agents", imports=("gym", "tdw", "unity_simulator"), gym_ids=("transport_challenge-v0",),
                  env_classes=2, track="robots", category="Agent框架", role="任务环境")
        family, _marker, notes = T.structural_family(f)
        self.assertIsNone(family)
        self.assertTrue(any("tdw" in n for n in notes))
        # softgym: gym envs on NVIDIA FleX through the compiled pyflex module
        flex = facts("softgym", imports=("gym", "pyflex"), gym_ids=("PourWater-v0",), env_classes=1, track="robots")
        self.assertIsNone(T.structural_family(flex)[0])

    def test_a_client_of_generic_networking_is_no_direct_driver(self):
        # labdaemon: the only device evidence is an exported HTTP client of the framework's own server
        client = entry_class(score=13, transport=("requests",), symbol="labdaemon.server.client:ServerAPI")
        f = facts("labdaemon", category="控制框架", role="控制器", entries=[client])
        self.assertTrue(T.device_evidence(f).startswith("exported class"))
        self.assertNotEqual(decide(f).strategy, "direct-driver")
        serial = entry_class(score=13, transport=("serial",), symbol="pump.dev:Pump")
        self.assertEqual(decide(facts("pump", category="控制框架", role="控制器", entries=[serial])).strategy,
                         "direct-driver")

    def test_newton_is_an_external_engine(self):
        f = facts("omnisim", imports=("mujoco", "newton"), mjcf=12, track="robots", category="完整环境", role="任务环境")
        family, _marker, notes = T.structural_family(f)
        self.assertIsNone(family)
        self.assertTrue(any("newton" in n for n in notes))


if __name__ == "__main__":
    unittest.main()
