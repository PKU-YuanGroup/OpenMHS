#!/usr/bin/env python3
"""Task cards (MHS/registry/taskcards.py) on synthetic facts: field rules, waves, ranks, pilot pool.

No corpus and no git: every input is built here.
"""
from __future__ import annotations

import copy
import math
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
REG = os.path.abspath(os.path.join(HERE, ".."))
MHS = os.path.abspath(os.path.join(REG, ".."))
sys.path.insert(0, REG)
sys.path.insert(0, os.path.join(MHS, "sdk", "src"))

import licenses as L  # noqa: E402
import taskcards as TC  # noqa: E402
import triage as T  # noqa: E402
from mhs import _ids  # noqa: E402
from mhs.schema import SchemaStore  # noqa: E402

STORE = SchemaStore(os.path.join(MHS, "schema"), extra_roots=[os.path.join(REG, "schema")])
COMMIT = "0123456789abcdef0123456789abcdef01234567"


def entry(symbol="bath.device:Bath", file="bath/device.py", line=12, methods=("get_temperature", "set_temperature",
          "set_gain", "start", "stop", "close", "write"), members=(), score=14, api=6, exported=True, bases=("Device",)):
    methods = sorted(methods)
    return {"symbol": symbol, "file": file, "line": line, "score": score, "bases": list(bases), "methods": methods,
            "members": list(members), "api_methods": [m for m in methods if m not in ("close",)], "api": api,
            "exported": exported, "async": False, "transport": ["serial"]}


def scan(entries=(), root_files=("pyproject.toml",), gym=(), mocks=(), limits=(), imports=("serial",), mjcf=(),
         tests=(), buildable=True, python_requires=">=3.9", readme_names=(), mjcf_main=(), env_entries=(),
         imports_core=None, artifacts=()):
    return {
        "scan_version": 7, "tree": ["README.md"], "truncated": False,
        "counts": {"files": 10, "python": 5, "code": 0, "notebooks": 0, "executables": 0, "installers": 0,
                   "archives": 0, "docs": 1, "total": 10},
        "readme": {"path": "README.md", "code_names": list(readme_names), "download_cta": [], "lure_words": [],
                   "artifact_downloads": list(artifacts)},
        "python": {"files": 5, "parsed": 5, "failed": 0, "skipped": 0, "imports": sorted(imports),
                   "imports_core": sorted(imports if imports_core is None else imports_core),
                   "imports_unparsed": [], "gym_ids": [g["id"] for g in gym], "gym_id_count": len(gym),
                   "gym_ids_aux": [], "gym_entries": list(gym), "env_classes": len(env_entries),
                   "env_entries": list(env_entries), "classes": len(entries),
                   "entry_classes": list(entries), "entry_more": [], "exported_names": []},
        "markers": {"package_xml": 0, "package_xml_paths": [], "launch_files": 0, "urdf": 0, "mjcf": len(mjcf),
                    "mjcf_aux": 0, "mjcf_paths": list(mjcf), "mjcf_main": list(mjcf_main),
                    "unity_project": False, "unreal_project": False,
                    "root_build_files": list(root_files), "has_tests": bool(tests), "test_dirs": list(tests)},
        "license": {"files": ["LICENSE"], "spdx": "MIT", "file": "LICENSE"},
        "install": {"python_requires": python_requires, "console_scripts": [], "requirements": [],
                    "pyproject_buildable": buildable, "declared_license": []},
        "mocks": list(mocks), "limit_hints": list(limits),
    }


def facts(name="bath", owner="acme", track="labs", scan_facts=None, stars=10):
    return T.RepoFacts(package_id=f"gh.{owner}/{name}", local_path=f"{track}/{owner}/{name}", track=track,
                       owner=owner, repo=name, tier="B", families=["python-object"], stars=stars,
                       catalog={"category": "", "adapter_role": ""}, analyst={},
                       git={"repo_url": f"https://github.com/{owner}/{name}", "commit": COMMIT},
                       scan=scan_facts if scan_facts is not None else scan([entry()]))


def decision(f, strategy="direct-driver", role="device-driver", family="python-object", reason="PY_SDK_WITH_ENTRY",
             **extra):
    d = T.Decision(package_id=f.package_id, strategy=strategy, role=role, reason_code=reason, rule=10,
                   family=family, **extra)
    return T._finish(f, d)


def record(f, modes=("hardware",)):
    return {"package_id": f.package_id, "local_path": f.local_path, "repo_url": f"https://github.com/{f.owner}/{f.repo}",
            "modes": list(modes), "stars": f.stars}


LIC_MIT = L.resolve("MIT", None)


def card(f, d, modes=("hardware",), lic=LIC_MIT, **kw):
    lock = {"repo_url": f.git["repo_url"], "commit": COMMIT}
    return TC.build_card(record(f, modes), d, f, lock, lic, **kw)


class CardFieldTests(unittest.TestCase):
    def errors(self, c):
        return STORE.validate(c, "taskcard.schema.json")

    def test_direct_driver_card_validates_and_follows_the_handoff(self):
        f = facts()
        c = card(f, decision(f))
        self.assertEqual(self.errors(c), [])
        self.assertEqual(c["$schema"], _ids.SCHEMA_BASE + "taskcard.schema.json")
        self.assertEqual(c["driver_dir"], "MHS/drivers/labs/acme__bath")
        self.assertEqual(c["acceptance"], "python3 -m mhs.driver check MHS/drivers/labs/acme__bath --backend fake")
        self.assertEqual((c["helper"], c["helper_status"], c["blocked_on"]), ("PythonObjectDriver", "available", []))
        self.assertEqual(c["exemplar"], "MHS/drivers/labs/tiagocoutinho__julabo")
        self.assertEqual(c["upstream"]["commit"], COMMIT)

    def test_entry_symbols_come_from_the_ast_only(self):
        f = facts(scan_facts=scan([entry()], readme_names=("Bath",)))
        c = card(f, decision(f))
        self.assertEqual(c["entry_symbols"], [{"symbol": "bath.device:Bath", "file": "bath/device.py", "line": 12,
                                               "confidence": "ast"}])
        for sym in c["entry_symbols"]:
            self.assertFalse(sym["file"].endswith("__init__.py") and sym["line"] == 1)
            self.assertNotIn("README", sym["file"])
        none = facts(scan_facts=scan([]))
        c2 = card(none, decision(none))
        self.assertEqual(c2["entry_symbols"], [])
        self.assertIn("entry_symbol", c2["needs_recon"])

    def test_robot_track_uses_the_xarm_exemplar(self):
        f = facts(track="robots")
        self.assertEqual(card(f, decision(f))["exemplar"], "MHS/drivers/robots/xarm-developer__xarm-python-sdk")

    def test_gym_registrations_are_the_entry_of_a_gymnasium_card(self):
        gym = [{"id": "Toy-v1", "entry_point": "toy.envs.toy:ToyEnv", "file": "toy/__init__.py", "line": 4,
                "class_file": "toy/envs/toy.py", "class_line": 30}]
        f = facts("toy", scan_facts=scan([entry()], gym=gym, imports=("gymnasium",)))
        c = card(f, decision(f, strategy="family-config", role="sim-env", family="gymnasium", reason="family:gymnasium"),
                 modes=("simulated",))
        self.assertEqual(self.errors(c), [])
        self.assertEqual(c["entry_symbols"], [{"symbol": "toy.envs.toy:ToyEnv", "file": "toy/envs/toy.py", "line": 30,
                                               "confidence": "ast"}])
        self.assertEqual(c["hints"]["candidate_classes"], ["cap.world.reset.v1", "cap.world.step.v1", "cap.world.seed.v1"])
        self.assertEqual(c["safety"], {"expected_mode": "simulated", "risk_floor": "R0", "limit_hints": []})
        self.assertEqual(c["mock_strategy"]["preferred"], "upstream-sim")
        self.assertEqual(c["exemplar"], "MHS/drivers/robots/farama-foundation__gymnasium")
        # a simulator without a resolvable registration has no device-class entry symbol; its main model is typed
        arm = {"file": "models/arm.xml", "line": 2, "kind": "robot"}
        f2 = facts("toy2", scan_facts=scan([entry()], imports=("mujoco",), mjcf=("models/arm.xml", "models/mug.xml"),
                                           mjcf_main=[arm]))
        c2 = card(f2, decision(f2, strategy="family-config", role="twin-candidate", family="mujoco",
                               reason="family:mujoco"), modes=("simulated",))
        self.assertEqual(self.errors(c2), [])
        self.assertEqual(c2["entry_symbols"], [])
        self.assertEqual(c2["models"], [arm])
        self.assertEqual(c2["hints"]["actions"], ["MJCF robot model models/arm.xml:2"])
        self.assertEqual(c2["mock_strategy"]["hints"][0], "models/arm.xml:2 MJCF robot model")
        self.assertNotIn("entry_symbol", c2["needs_recon"])
        self.assertEqual(c2["hints"]["candidate_classes"], ["cap.world.reset.v1", "cap.world.step.v1"])
        self.assertTrue(TC.has_entry(c2))
        # object assets only: no model, recon names one; environment classes are the entry of a recon card
        env = {"symbol": "libero.envs.wrapper:OffScreenRenderEnv", "file": "libero/envs/wrapper.py", "line": 152,
               "score": 5, "bases": ["ControlEnv"]}
        f3 = facts("toy3", scan_facts=scan([entry()], imports=("mujoco", "robosuite"), mjcf=("assets/faucet.xml",),
                                           env_entries=[env]))
        c3 = card(f3, decision(f3, strategy="family-config", role="sim-env", family="mujoco", reason="family:mujoco"),
                  modes=("simulated",))
        self.assertEqual(c3["models"], [])
        self.assertIn("model", c3["needs_recon"])
        self.assertEqual(c3["entry_symbols"], [{"symbol": "libero.envs.wrapper:OffScreenRenderEnv",
                                                "file": "libero/envs/wrapper.py", "line": 152, "confidence": "ast"}])
        self.assertFalse(TC.has_entry(dict(c3, entry_symbols=[])))

    def test_install_commands_need_a_root_file(self):
        cases = [((), []), (("setup.py",), ["pip install ."]), (("pyproject.toml",), ["pip install ."]),
                 (("requirements.txt",), ["pip install -r requirements.txt"]),
                 (("setup.py", "requirements.txt"), ["pip install ."]), (("package.xml",), []),
                 (("CMakeLists.txt",), [])]
        for roots, want in cases:
            f = facts(scan_facts=scan([entry()], root_files=roots))
            self.assertEqual(card(f, decision(f))["install"]["commands"], want, roots)
        f = facts(scan_facts=scan([entry()], root_files=("pyproject.toml",), buildable=False))
        self.assertEqual(card(f, decision(f))["install"]["commands"], [])
        self.assertEqual(TC.python_spec(">= 3.8"), ">=3.8")
        self.assertEqual(TC.python_spec("3.10"), ">=3.10")
        self.assertEqual(TC.python_spec(">=3.6.*"), ">=3.6")
        self.assertIsNone(TC.python_spec("python3"))

    def test_hints_map_native_names_to_catalogue_classes(self):
        f = facts()
        c = card(f, decision(f))
        classes = c["hints"]["candidate_classes"]
        self.assertIn("cap.thermal.setpoint.v1", classes)       # set_temperature
        self.assertIn("cap.measure.temperature.v1", classes)    # get_temperature
        self.assertIn("cap.device.configure.v1", classes)       # set_gain: a setter without a better class
        self.assertEqual(c["safety"]["risk_floor"], "R2")       # catalogue risk of thermal.setpoint
        self.assertIn("Bath.set_gain", c["hints"]["writes"])
        self.assertNotIn("Bath.close", c["hints"]["actions"] + c["hints"]["writes"] + c["hints"]["reads"])
        self.assertNotIn("Bath.write", c["hints"]["writes"])    # raw I/O is not a parameter

    def test_class_rules(self):
        ctx = set()
        self.assertEqual(TC.class_for("set_servo_angle", "write", "robots", ctx), "cap.motion.joint_position.v1")
        self.assertEqual(TC.class_for("set_position", "write", "robots", ctx), "cap.motion.cartesian_pose.v1")
        self.assertEqual(TC.class_for("emergency_stop", "action", "robots", ctx), None)
        self.assertEqual(TC.class_for("aspirate", "action", "labs", ctx), "cap.fluid.aspirate.v1")
        self.assertEqual(TC.class_for("pick_up_tips", "action", "labs", ctx), None)   # x-cap until a class exists
        self.assertEqual(TC.class_for("set_point_1", "attribute", "labs", {"temperature", "bath"}),
                         "cap.thermal.setpoint.v1")
        self.assertEqual(TC.class_for("read_voltage", "read", "labs", ctx), "cap.measure.voltage.v1")
        self.assertEqual(TC.class_for("get_frequency", "read", "labs", ctx), "cap.sensing.read.v1")
        self.assertEqual(TC.class_for("set_frequency", "write", "labs", ctx), "cap.device.configure.v1")
        stop_only = facts(scan_facts=scan([entry(methods=("stop", "get_status"))]))
        self.assertNotIn("cap.motion.stop.v1", card(stop_only, decision(stop_only))["hints"]["candidate_classes"])
        mover = facts(scan_facts=scan([entry(methods=("move_absolute", "stop"))]))
        self.assertIn("cap.motion.stop.v1", card(mover, decision(mover))["hints"]["candidate_classes"])

    def test_mock_strategy(self):
        device_mock = {"kind": "class", "file": "bath/sim.py", "line": 3, "symbol": "bath.sim:SimBath"}
        test_mock = {"kind": "class", "file": "tests/test_bath.py", "line": 9, "symbol": "tests.test_bath:FakeBath"}
        f = facts(scan_facts=scan([entry()], mocks=[device_mock, test_mock], tests=("tests",)))
        m = card(f, decision(f))["mock_strategy"]
        self.assertEqual(m, {"preferred": "upstream-sim", "hints": ["bath/sim.py:3 SimBath"], "upstream_tests": "tests"})
        f = facts(scan_facts=scan([entry()], mocks=[test_mock]))
        self.assertEqual(card(f, decision(f))["mock_strategy"]["preferred"], "fake")
        f = facts(scan_facts=scan([entry()]))
        c = card(f, decision(f, strategy="family-config", family="scpi", reason="family:scpi"))
        self.assertEqual(c["mock_strategy"]["preferred"], "transcript")
        self.assertEqual(c["exemplar"], "MHS/drivers/labs/thinksrs__srsinst.sr860")

    def test_limit_hints_drop_error_codes(self):
        limits = [{"file": "bath/device.py", "line": 5, "name": "MAX_TEMP", "value": "150"},
                  {"file": "bath/codes.py", "line": 2, "name": "JOINT_LIMIT", "value": "-7"},
                  {"file": "bath/device.py", "line": 6, "name": "RX_LEN_MAX", "value": "50"}]
        f = facts(scan_facts=scan([entry()], limits=limits))
        c = card(f, decision(f))
        self.assertEqual(c["safety"]["limit_hints"], ["bath/device.py:5 MAX_TEMP = 150"])
        self.assertNotIn("limit_sources", c["needs_recon"])
        bare = facts(scan_facts=scan([entry()]))
        self.assertIn("limit_sources", card(bare, decision(bare))["needs_recon"])

    def test_blocked_helper_and_other_decisions_validate(self):
        f = facts()
        mm = card(f, decision(f, strategy="family-config", family="pymmcore-plus", reason="family:pymmcore-plus"))
        self.assertEqual((mm["helper"], mm["helper_status"], mm["blocked_on"]),
                         (None, "blocked", ["helper:pymmcore-plus"]))
        self.assertIsNone(mm["exemplar"])
        self.assertEqual(self.errors(mm), [])
        ros = card(f, decision(f, strategy="family-config", family="ros", reason="family:ros"))
        self.assertEqual((ros["helper"], ros["helper_status"], ros["blocked_on"]), ("RosDriver", "available", []))
        self.assertEqual(ros["exemplar"], "MHS/drivers/robots/avidbots__flatland")
        self.assertEqual(self.errors(ros), [])
        lure = decision(f, strategy="skip", role="not-device", family=None, reason="skip:quarantine", quarantine=True,
                        evidence=["README download call-to-action to https://x.github.io/a with 0 source file(s)"])
        q = card(f, lure)
        self.assertEqual((q["quarantine"], q["blocked_on"], q["entry_symbols"]), (True, ["QUARANTINE"], []))
        self.assertTrue(q["skip_reason"].startswith("README download"))
        self.assertEqual(self.errors(q), [])
        for strategy, role, reason in (("untriaged", "device-driver", "untriaged:weak_entry"),
                                       ("reference", "host", "reference:host"),
                                       ("bridge-runtime", "transport", "bridge-runtime:scpi")):
            c = card(f, decision(f, strategy=strategy, role=role, family=None, reason=reason))
            self.assertEqual(self.errors(c), [], strategy)
            if strategy == "untriaged":
                self.assertIn("decision", c["needs_recon"])
                self.assertEqual(c["timebox_min"], 30)
            else:
                self.assertEqual(c["hints"]["candidate_classes"], [])
        dup = card(f, decision(f, strategy="skip", role="device-driver", family=None, reason="skip:duplicate_of",
                               variant_of="gh.acme/upstream", evidence=["same HEAD commit 0123 as gh.acme/upstream"]))
        self.assertEqual(self.errors(dup), [])
        self.assertIn("gh.acme/upstream", dup["skip_reason"])

    def test_qcodes_and_ophyd_helpers_are_available_with_their_exemplars(self):
        f = facts()
        for family, helper, exemplar in (("qcodes", "QcodesDriver", "MHS/drivers/labs/qcodes__qcodes_contrib_drivers"),
                                         ("ophyd", "OphydDriver", "MHS/drivers/labs/bcda-aps__apstools")):
            c = card(f, decision(f, strategy="family-config", family=family, reason=f"family:{family}"))
            self.assertEqual((c["helper"], c["helper_status"], c["blocked_on"], c["exemplar"]),
                             (helper, "available", [], exemplar))
            self.assertEqual(self.errors(c), [])

    def test_publish_review_follows_the_licence(self):
        f = facts()
        for raw, want in (("MIT", "not_required"), ("GPL-3.0", "not_required"), ("AGPL-3.0", "required"),
                          ("SSPL-1.0", "required"), ("unknown", "required")):
            c = card(f, decision(f), lic=L.resolve(raw, None))
            self.assertEqual(c["publish_review"], want, raw)
            self.assertEqual(self.errors(c), [], raw)
        review = card(f, decision(f), lic=L.resolve("MIT（运行需 NI 专有驱动）", None))   # proprietary runtime
        self.assertEqual(review["publish_review"], "required")

    def test_an_override_can_require_a_publication_review_but_never_waive_one(self):
        f = facts()
        for raw in ("MIT", "GPL-3.0", "AGPL-3.0"):
            c = card(f, decision(f, publish_review="required"), lic=L.resolve(raw, None))
            self.assertEqual(c["publish_review"], "required", raw)
            self.assertEqual(c["upstream"]["license_spdx"], raw, "the licence evidence itself is unchanged")
            self.assertEqual(self.errors(c), [], raw)
        self.assertEqual(card(f, decision(f), lic=L.resolve("MIT", None))["publish_review"], "not_required")

    def test_reviewed_capability_classes_replace_the_scan_and_set_the_risk_floor(self):
        camera = entry("cam.node:CameraNode", "cam/node.py", 27,
                       methods=("set_camera_parameters", "get_parameter_value", "initialize_capture_queue"))
        f = facts("picam", track="robots", scan_facts=scan([camera]))
        scanned = card(f, decision(f, strategy="family-config", family="ros", reason="family:ros"))
        self.assertIn("cap.device.configure.v1", scanned["hints"]["candidate_classes"])
        self.assertEqual(scanned["safety"]["risk_floor"], "R1")
        self.assertIn("motion", scanned["needs_recon"])
        reviewed = card(f, decision(f, strategy="family-config", family="ros", reason="family:ros",
                                    capability_classes=["cap.sensing.image.v1"]))
        self.assertEqual(reviewed["hints"]["candidate_classes"], ["cap.sensing.image.v1"])
        self.assertEqual(reviewed["hints"]["writes"], scanned["hints"]["writes"], "the scan's member hints stay")
        self.assertEqual(reviewed["safety"]["risk_floor"], "R0")
        self.assertFalse({"motion", "limit_sources", "capabilities"} & set(reviewed["needs_recon"]))
        self.assertEqual(self.errors(reviewed), [])
        for wrong in (["cap.sensing.nonexistent.v1"], ["cap.device.describe.v1"]):   # unknown, deprecated
            with self.subTest(wrong=wrong):
                with self.assertRaises(ValueError):
                    card(f, decision(f, strategy="family-config", family="ros", reason="family:ros",
                                     capability_classes=wrong))

    def test_omit_sim_contract_drops_models_and_world_classes(self):
        model = {"file": "src/vendor_sim/etc/robot_mujoco.xml", "line": 1, "kind": "scene"}
        f = facts("arm", track="robots", scan_facts=scan(
            [], imports=("rclpy",), mjcf=(model["file"],), mjcf_main=[model],
            tests=("src/desc/test",), root_files=()))
        kw = dict(strategy="family-config", role="sim-env", family="ros", reason="family:ros")
        scanned = card(f, decision(f, **kw), modes=("simulated",))
        self.assertEqual(scanned["models"], [model])
        self.assertEqual(scanned["hints"]["candidate_classes"],
                         ["cap.world.reset.v1", "cap.world.step.v1", "cap.world.seed.v1"])
        self.assertEqual(scanned["hints"]["actions"], [f"MJCF scene model {model['file']}:1"])
        self.assertEqual(scanned["mock_strategy"]["preferred"], "upstream-sim")
        dropped = card(f, decision(f, omit_sim_contract=True, **kw), modes=("simulated",))
        self.assertEqual(dropped["models"], [])
        self.assertEqual(dropped["hints"], {"reads": [], "writes": [], "actions": [], "candidate_classes": []})
        self.assertEqual(dropped["mock_strategy"],
                         {"preferred": "fake", "hints": [], "upstream_tests": "src/desc/test"})
        self.assertEqual(dropped["safety"], {"expected_mode": "simulated", "risk_floor": "R0", "limit_hints": []})
        self.assertIn("capabilities", dropped["needs_recon"])
        self.assertEqual(self.errors(dropped), [])
        named = card(f, decision(f, omit_sim_contract=True, capability_classes=["cap.sensing.read.v1"], **kw),
                     modes=("simulated",))
        self.assertEqual(named["models"], [])
        self.assertEqual(named["hints"]["candidate_classes"], ["cap.sensing.read.v1"])
        self.assertEqual(named["mock_strategy"]["preferred"], "fake")
        self.assertNotIn("capabilities", named["needs_recon"])
        self.assertEqual(self.errors(named), [])

    def test_gpu_platform_and_english(self):
        f = facts(scan_facts=scan([entry()], imports=("serial", "isaacgym")))
        self.assertTrue(card(f, decision(f))["install"]["gpu"])
        self.assertTrue(TC.needs_gpu(facts(), "需要 NVIDIA GPU"))         # needs an NVIDIA GPU
        self.assertFalse(TC.needs_gpu(facts(), "无需 GPU，CPU 即可"))      # no GPU needed
        self.assertFalse(TC.needs_gpu(facts(), "GPU optional"))
        win = facts(scan_facts=scan([entry()], imports=("serial", "win32com")))
        self.assertEqual(card(win, decision(win))["install"]["platform"], "windows")
        text = TC.english("catalogue category '策略/算法' with no env registration")
        self.assertIsNone(TC.CJK_RE.search(text))
        self.assertIn("with no env registration", text)

    # --- exemplars-service (2026-11-04): the mcp-client family is available with its exemplar ---
    def test_mcp_client_family_is_available_with_its_exemplar(self):
        f = facts()
        mcp = card(f, decision(f, strategy="family-config", family="mcp-client", reason="family:mcp-client"))
        self.assertEqual((mcp["helper"], mcp["helper_status"], mcp["blocked_on"]), ("McpClientDriver", "available", []))
        self.assertEqual(mcp["exemplar"], "MHS/drivers/labs/mattjax16__rigol-dho-mcp")
        self.assertEqual(self.errors(mcp), [])
        for family in ("http",):
            held = card(f, decision(f, strategy="family-config", family=family, reason="family:" + family))
            self.assertEqual((held["helper"], held["helper_status"], held["blocked_on"]), (None, "blocked", ["helper:" + family]))
    # --- end exemplars-service ---

    # --- w1-waiting-routing (2026-11-05): the sila2 family is available with its sila-testing exemplar ---
    def test_sila2_family_is_available_with_its_exemplar(self):
        f = facts()
        sila = card(f, decision(f, strategy="family-config", family="sila2", reason="family:sila2"))
        self.assertEqual((sila["helper"], sila["helper_status"], sila["blocked_on"]), ("Sila2Driver", "available", []))
        self.assertEqual(sila["exemplar"], "MHS/drivers/labs/anguyen-23__sila-testing")
        self.assertEqual(self.errors(sila), [])
        for family in ("http", "pymmcore-plus", "mavlink", "lerobot"):
            held = card(f, decision(f, strategy="family-config", family=family, reason="family:" + family))
            self.assertEqual((held["helper"], held["helper_status"], held["blocked_on"]), (None, "blocked", ["helper:" + family]))
    # --- end w1-waiting-routing ---


class WaveAndRankTests(unittest.TestCase):
    def build(self, specs):
        cards, decisions, fs, stars = {}, {}, {}, {}
        for name, kw in specs:
            f = facts(name, **{k: v for k, v in kw.items() if k in ("track", "scan_facts", "stars")})
            d = decision(f, **{k: v for k, v in kw.items() if k in ("strategy", "role", "family", "reason", "wave",
                                                                   "partner", "quarantine")})
            fs[f.package_id], decisions[f.package_id], stars[f.package_id] = f, d, f.stars
            cards[f.package_id] = card(f, d, modes=kw.get("modes", ("hardware",)), lic=kw.get("lic", LIC_MIT))
        return cards, decisions, fs, stars

    def test_rank_formula(self):
        f = facts(stars=99, scan_facts=scan([entry()], tests=("tests",)))
        c = card(f, decision(f))
        comp = TC.rank_components(c, partner=True, stars=99, has_tests=True)
        self.assertAlmostEqual(comp["rank_score"], round(40 + 20 + 10 + 8 + 5 * math.log10(100), 4))
        c2 = copy.deepcopy(c)
        c2["install"]["gpu"] = True
        c2["upstream"]["license_class"] = "unknown"
        self.assertAlmostEqual(TC.rank_components(c2, False, 0, False)["rank_score"], 20 + 10 - 15 - 20)

    def test_waves(self):
        specs = [
            ("exemplar", dict(wave=0)),
            ("strict", dict(stars=5)),
            ("nolicence", dict(lic=L.resolve("unknown", None))),
            ("blocked", dict(strategy="family-config", family="pymmcore-plus", reason="family:pymmcore-plus")),
            ("recon", dict(strategy="untriaged", family=None, reason="untriaged:weak_entry")),
            ("engine", dict(strategy="untriaged", family=None, reason="untriaged:no_entry_class",
                            scan_facts=scan([], imports=("isaacgym",)))),
            ("gpu", dict(scan_facts=scan([entry()], imports=("serial", "cupy")))),
            ("skipped", dict(strategy="skip", role="not-device", family=None, reason="skip:tooling")),
        ]
        cards, decisions, fs, stars = self.build(specs)
        TC.assign_waves(cards, decisions, fs, stars, pilot_size=0)
        wave = {pid.split("/")[1]: c["wave"] for pid, c in cards.items()}
        self.assertEqual(wave, {"exemplar": 0, "strict": 2, "nolicence": 3, "blocked": 5, "recon": 4, "engine": 6,
                                "gpu": 6, "skipped": 9})
        by_wave = {}
        for c in cards.values():
            by_wave.setdefault(c["wave"], []).append(c["rank"])
        for ranks in by_wave.values():
            self.assertEqual(sorted(ranks), list(range(1, len(ranks) + 1)))

    def test_rank_ties_break_by_package_id_and_pilot_is_balanced(self):
        specs = []
        arm = entry("arm.robot:Arm", "arm/robot.py", methods=("move_to", "get_position", "stop", "set_speed", "close"))
        for i in range(12):
            specs.append((f"inst{i:02d}", dict()))
            specs.append((f"robot{i:02d}", dict(track="robots", scan_facts=scan([arm]))))
            specs.append((f"scpi{i:02d}", dict(strategy="family-config", family="scpi", reason="family:scpi")))
            specs.append((f"gym{i:02d}", dict(strategy="family-config", role="sim-env", family="gymnasium",
                                              reason="family:gymnasium", modes=("simulated",),
                                              scan_facts=scan([], gym=[{"id": f"G{i}-v0", "entry_point": "g.e:Env",
                                                                        "file": "g/__init__.py", "line": 1,
                                                                        "class_file": "g/e.py", "class_line": 3,
                                                                        "class_resolved": "defined"}],
                                                              imports=("gymnasium",)))))
        specs.append(("julabo", dict(wave=0)))
        cards, decisions, fs, stars = self.build(specs)
        result = TC.assign_waves(cards, decisions, fs, stars)
        pilot = result["pilot"]
        self.assertEqual(len(pilot), 40)
        self.assertEqual({b: sum(1 for p in pilot if p["bucket"] == b) for b in TC.PILOT_BUCKETS},
                         {b: 10 for b in TC.PILOT_BUCKETS})
        self.assertIn("gh.acme/julabo", [p["package_id"] for p in pilot])
        self.assertEqual(cards["gh.acme/julabo"]["wave"], 0)
        insts = sorted((c["rank"], pid) for pid, c in cards.items() if c["wave"] == 1 and "inst" in pid)
        self.assertEqual([pid for _r, pid in insts], sorted(pid for _r, pid in insts))   # equal scores: by id
        doc = TC.pilot_document(pilot, cards, "2026-10-20T00:00:00Z")
        self.assertEqual(doc["count"], 40)
        self.assertEqual(doc["candidates"][0]["task"], cards[doc["candidates"][0]["package_id"]])
        # a short bucket gives its slots to the others
        short = [(n, kw) for n, kw in specs if not n.startswith("robot") or n in ("robot00", "robot01")]
        cards, decisions, fs, stars = self.build(short)
        picked = TC.assign_waves(cards, decisions, fs, stars)["pilot"]
        self.assertEqual(len(picked), 39)     # 13 + 2 + 12 + 12 cards exist; every one is taken
        self.assertEqual(sum(1 for p in picked if p["bucket"] == "robot-sdk"), 2)
        self.assertEqual(sum(1 for p in picked if p["bucket"] == "direct-python-instrument"), 13)


class EntryRankingTests(unittest.TestCase):
    """Card-level ranking of AST classes (verification findings: enums, value types, MicroPython, transports)."""

    def ranked(self, entries, family="python-object", readme=()):
        f = facts(scan_facts=scan(list(entries), readme_names=readme))
        return [c["symbol"] for c in TC.ranked_classes(f, family)]

    def test_enums_constant_tables_and_value_types_rank_below_the_device(self):
        robot = entry("cozmo.robot:Robot", "cozmo/robot.py", 630, score=13, bases=("Dispatcher",))
        audio = entry("cozmo.audio:AudioEvents", "cozmo/audio.py", 46, methods=(), members=tuple(f"E{i}" for i in range(40)),
                      score=13, bases=("CladEnumWrapper",))
        matrix = entry("cozmo.util:Matrix44", "cozmo/util.py", 316, methods=("set_pos", "set_up"), score=13, bases=())
        self.assertEqual(self.ranked([audio, matrix, robot])[0], "cozmo.robot:Robot")

    def test_generated_microcontroller_and_test_classes(self):
        client = entry("pycozmo.client:Client", "pycozmo/client.py", 41, score=10, bases=())
        anim = dict(entry("pycozmo.CozmoAnim.AnimClip:AnimClip", "pycozmo/CozmoAnim/AnimClip.py", 7, score=14),
                    generated=True)
        board = dict(entry("demo.lib.as7341:AS7341", "src/demo/lib/as7341.py", 170, score=14), microcontroller=True)
        test = entry("typing_tests.props:TestProps", "typing_tests/props.py", 3, score=14)
        ranked = self.ranked([anim, board, test, client])
        self.assertEqual(ranked[0], "pycozmo.client:Client")
        self.assertNotIn("demo.lib.as7341:AS7341", ranked)          # runs on the board, never the host entry
        self.assertNotIn("typing_tests.props:TestProps", ranked)

    def test_transport_layers_mocks_and_base_classes_rank_below_the_instrument(self):
        node = entry("tecancavro.transport:TecanAPINode", "tecancavro/transport.py", 20, score=14)
        pump = entry("tecancavro.models:XCaliburD", "tecancavro/models.py", 40, score=12, bases=("SyringeBase",))
        self.assertEqual(self.ranked([node, pump], family="serial")[0], "tecancavro.models:XCaliburD")
        base = entry("pycont.controller:C3000Controller", "pycont/controller.py", 100, score=14, bases=())
        virtual = entry("pycont.controller:VirtualC3000Controller", "pycont/controller.py", 400, score=14,
                        bases=("C3000Controller",))
        self.assertEqual(self.ranked([virtual, base])[0], "pycont.controller:C3000Controller")
        scpi = entry("lib.core.SCPI:SCPIDevice", "lib/core/SCPI.py", 10, score=20, bases=())
        awg = entry("lib.devices.Agilent:AWG33220A", "lib/devices/Agilent.py", 10, score=17, bases=("SCPIDevice",))
        self.assertEqual(self.ranked([scpi, awg], family="scpi")[0], "lib.devices.Agilent:AWG33220A")

    def test_device_nouns_and_copies(self):
        feature = entry("sb.features.gpio:SeaBreezeGPIOFeature", "sb/features/gpio.py", 9, score=13, bases=())
        spectro = entry("sb.spectrometers:Spectrometer", "sb/spectrometers.py", 97, methods=("open", "close", "spectrum"),
                        score=5, bases=())
        self.assertEqual(self.ranked([feature, spectro], readme=("Spectrometer",))[0], "sb.spectrometers:Spectrometer")
        a = entry("x.a.lib.chip:Chip", "x/a/lib/chip.py", 5)
        b = entry("x.b.lib.chip:Chip", "x/b/lib/chip.py", 5)
        self.assertEqual(len(self.ranked([a, b])), 1)                  # a copied file is listed once


class GymEntryConfidenceTests(unittest.TestCase):
    def test_unlocated_or_external_registration_is_recon(self):
        gym = [{"id": "Tac-v0", "entry_point": "isaaclab.envs:ManagerBasedRLEnv", "file": "tasks/__init__.py",
                "line": 20, "module_in_repo": False},
               {"id": "Toy-v1", "entry_point": "toy.envs:ToyEnv", "file": "toy/__init__.py", "line": 4,
                "class_file": "toy/envs/toy.py", "class_line": 30, "class_resolved": "reexport"}]
        f = facts("toy", scan_facts=scan([], gym=gym, imports=("gymnasium",)))
        c = card(f, decision(f, strategy="family-config", role="sim-env", family="gymnasium", reason="family:gymnasium"),
                 modes=("simulated",))
        self.assertEqual(STORE.validate(c, "taskcard.schema.json"), [])
        self.assertEqual(c["entry_symbols"], [
            {"symbol": "toy.envs:ToyEnv", "file": "toy/envs/toy.py", "line": 30, "confidence": "ast"},
            {"symbol": "isaaclab.envs:ManagerBasedRLEnv", "file": "tasks/__init__.py", "line": 20, "confidence": "recon"}])


class DispatchRuleTests(unittest.TestCase):
    def test_near_empty_dispatchable_card_is_blocked_on_recon(self):
        f = facts("temi", scan_facts=scan([], root_files=()))
        c = card(f, decision(f))
        self.assertEqual(STORE.validate(c, "taskcard.schema.json"), [])
        self.assertEqual(c["blocked_on"], [TC.RECON_BLOCK])
        self.assertFalse(TC.dispatch_ready(c))
        self.assertEqual(TC.base_wave(c, decision(f), f), TC.WAVE_RECON)

    def test_passing_package_keeps_its_wave_and_is_not_dispatched_again(self):
        f = facts()
        c = card(f, decision(f), package_status="pass")
        self.assertEqual(STORE.validate(c, "taskcard.schema.json"), [])
        self.assertTrue(TC.dispatch_ready(c))
        self.assertFalse(TC.dispatchable_now(c))
        self.assertEqual(TC.base_wave(c, decision(f), f), TC.WAVE_STRICT)
        blocked = card(f, decision(f), overlay_blocked=["INSTALL_FAILED"], package_status="blocked")
        self.assertEqual(blocked["blocked_on"], ["INSTALL_FAILED"])
        self.assertFalse(TC.dispatchable_now(blocked))
        self.assertEqual(card(f, decision(f), package_status="in_progress")["package_status"], "in_progress")

    def test_expected_mode_is_null_for_never_dispatched_cards_without_modes(self):
        f = facts("tvb")
        skip = decision(f, strategy="skip", role="not-device", family=None, reason="skip:peripheral")
        c = card(f, skip, modes=())
        self.assertIsNone(c["safety"]["expected_mode"])
        self.assertEqual(STORE.validate(c, "taskcard.schema.json"), [])
        sim = decision(f, strategy="untriaged", role="sim-env", family=None, reason="untriaged:weak_entry")
        self.assertEqual(card(f, sim, modes=())["safety"]["expected_mode"], "simulated")

    def test_limit_hints_drop_training_settings_and_appear_on_hardware_cards_only(self):
        limits = [{"file": "pkg/device.py", "line": 5, "name": "MAX_TEMP", "value": "150"},
                  {"file": "pkg/device.py", "line": 6, "name": "MAX_REDIRECTS", "value": "3"},
                  {"file": "pkg/device.py", "line": 7, "name": "max_grad_norm", "value": "0.5"},
                  {"file": "pkg/train/ppo.py", "line": 8, "name": "MAX_SPEED", "value": "2"},
                  {"file": "pkg/device.py", "line": 9, "name": "MAX_LITERS", "value": "2"}]
        f = facts(scan_facts=scan([entry()], limits=limits))
        self.assertEqual(TC.limit_hints(f), ["pkg/device.py:5 MAX_TEMP = 150", "pkg/device.py:9 MAX_LITERS = 2"])
        self.assertEqual(len(card(f, decision(f))["safety"]["limit_hints"]), 2)
        sim = card(f, decision(f, strategy="family-config", role="sim-env", family="gymnasium",
                               reason="family:gymnasium"), modes=("simulated",))
        self.assertEqual(sim["safety"]["limit_hints"], [])

    def test_pilot_needs_a_usable_entry(self):
        f = facts()
        c = card(f, decision(f))
        self.assertTrue(TC.pilot_ready(c))
        self.assertTrue(TC.pilot_entry_ok(c, f))
        dll = dict(entry(), transport=["ctypes"])
        g = facts("u12", scan_facts=scan([dll]))
        self.assertFalse(TC.pilot_entry_ok(card(g, decision(g)), g))   # a vendor DLL behind ctypes
        h = facts("noclass", scan_facts=scan([entry(methods=("run",), score=14)]))
        hc = card(h, decision(h))
        self.assertEqual(hc["hints"]["candidate_classes"], [])
        self.assertFalse(TC.pilot_ready(hc))
        self.assertFalse(TC.strict_ready(hc))


class VerificationFixTests(unittest.TestCase):
    """Card rules added after the second verification of 10b."""

    def test_mocks_and_dummies_are_not_entry_symbols_when_a_real_class_exists(self):
        dummy = entry("pyzaber.dummy_linear_slides:multiaxis_linear_slides", "pyzaber/dummy_linear_slides.py", 9,
                      score=16, methods=("move_absolute", "get_current_position", "set_position", "home"))
        real = entry("pyzaber.linear_slides:multiaxis_linear_slides", "pyzaber/linear_slides.py", 30, score=12,
                     methods=("move_absolute", "get_current_position", "set_position", "home"))
        mock = entry("drivers.KeysightN5182B:KeysightN5182BMock", "drivers/KeysightN5182B.py", 25, score=16)
        f = facts("pyzaber", scan_facts=scan([dummy, real, mock]))
        c = card(f, decision(f, strategy="family-config", family="serial", reason="family:serial"))
        self.assertEqual([e["symbol"] for e in c["entry_symbols"]], ["pyzaber.linear_slides:multiaxis_linear_slides"])
        only = facts("onlymock", scan_facts=scan([mock]))
        self.assertEqual([e["symbol"] for e in card(only, decision(only))["entry_symbols"]],
                         ["drivers.KeysightN5182B:KeysightN5182BMock"])

    def test_facade_ranks_above_the_class_it_wraps_and_members_feed_the_hints(self):
        inner = dict(entry("xarm.x3.xarm:XArm", "xarm/x3/xarm.py", 43, score=20, methods=("set_position", "get_position",
                                                                                          "set_servo_angle")),
                     composes=[])
        api = dict(entry("xarm.wrapper.xarm_api:XArmAPI", "xarm/wrapper/xarm_api.py", 14, score=15,
                         methods=("set_position", "get_position")), composes=[{"attr": "_arm", "class": "XArm"}])
        f = facts("xarm", track="robots", scan_facts=scan([inner, api], readme_names=("XArmAPI",)))
        self.assertEqual(TC.ranked_classes(f)[0]["symbol"], "xarm.wrapper.xarm_api:XArmAPI")
        robot = dict(entry("dobot.robot:DobotRobot", "dobot/robot.py", 25, methods=("enable_robot", "get_status",
                                                                                     "close")),
                     composes=[{"attr": "motion", "class": "Motion"}], composed_methods=["motion.MovJ", "motion.MovL"])
        g = facts("dobot", track="robots", scan_facts=scan([robot]))
        c = card(g, decision(g))
        self.assertIn("DobotRobot.motion.MovJ", c["hints"]["actions"])
        self.assertIn("cap.motion.joint_position.v1", c["hints"]["candidate_classes"])
        self.assertNotIn("motion", c["needs_recon"])

    def test_robot_hardware_card_without_a_motion_api_needs_recon_and_leaves_the_pilot(self):
        f = facts("sensor-arm", track="robots", scan_facts=scan([entry(methods=("get_status", "get_temperature"))]))
        c = card(f, decision(f))
        self.assertIn("motion", c["needs_recon"])
        self.assertFalse(TC.pilot_ready(c))
        lab = facts("bath")
        self.assertNotIn("motion", card(lab, decision(lab))["needs_recon"])

    def test_artifact_downloads_leave_strict_ready_and_the_pilot(self):
        arm = {"file": "models/scene.xml", "line": 1, "kind": "scene"}
        f = facts("kitchen", scan_facts=scan([], imports=("mujoco",), mjcf=("models/scene.xml",), mjcf_main=[arm],
                                             artifacts=("download_kitchen_assets",)))
        c = card(f, decision(f, strategy="family-config", role="sim-env", family="mujoco", reason="family:mujoco"),
                 modes=("simulated",))
        self.assertIn("artifacts", c["needs_recon"])
        self.assertTrue(TC.dispatch_ready(c))
        self.assertFalse(TC.strict_ready(c))
        self.assertFalse(TC.pilot_ready(c))

    def test_optional_gpu_paths_and_benchmark_scripts_need_no_gpu(self):
        f = facts(scan_facts=scan([entry()], imports=("serial", "cupy"), imports_core=("serial",)))
        self.assertFalse(card(f, decision(f))["install"]["gpu"])
        g = facts(scan_facts=scan([entry()], imports=("serial", "cupy")))
        self.assertTrue(card(g, decision(g))["install"]["gpu"])

    def test_gui_classes_are_never_entry_symbols(self):
        widget = entry("software.common.gui.widgets:AxisStatusDisplay", "software/common/gui/widgets.py", 46, score=12)
        f = facts("octoaxes", scan_facts=scan([widget]))
        c = card(f, decision(f, strategy="family-config", family="serial", reason="family:serial"))
        self.assertEqual(c["entry_symbols"], [])
        self.assertEqual(c["hints"]["candidate_classes"], [])      # nor the source of the hints
        self.assertIn("entry_symbol", c["needs_recon"])
        f2 = facts("octoaxes2", scan_facts=scan([widget], root_files=()))
        c2 = card(f2, decision(f2, strategy="family-config", family="serial", reason="family:serial"))
        self.assertIn(TC.RECON_BLOCK, c2["blocked_on"])           # no class, no install file: recon first

    def test_an_overrides_entry_symbols_replace_the_scan_and_lift_the_recon_block(self):
        widget = entry("software.common.gui.widgets:AxisStatusDisplay", "software/common/gui/widgets.py", 46, score=12)
        f = facts("octoaxes3", scan_facts=scan([widget], root_files=()))
        d = decision(f, strategy="family-config", family="serial", reason="override:recon")
        d.entry_symbols = [{"symbol": "hardware.serial_thread:SerialThread", "file": "software/common/hardware/serial_thread.py",
                            "line": 21}]
        c = card(f, d)
        self.assertEqual(c["entry_symbols"], [dict(d.entry_symbols[0], confidence="override")])
        self.assertNotIn(TC.RECON_BLOCK, c["blocked_on"])
        self.assertNotIn("entry_symbol", c["needs_recon"])

    def test_mujoco_py_is_a_system_dependency(self):
        model = {"file": "assets/robot.xml", "line": 1, "kind": "robot"}
        f = facts("legacy", scan_facts=scan([], imports=("mujoco_py", "gym"), mjcf=("assets/robot.xml",),
                                            mjcf_main=[model]))
        c = card(f, decision(f, strategy="family-config", role="sim-env", family="mujoco", reason="family:mujoco"),
                 modes=("simulated",))
        self.assertEqual(c["install"]["system_deps"], ["MuJoCo 2.1 binaries and a C compiler for mujoco-py"])
        self.assertFalse(TC.strict_ready(c))
        self.assertFalse(TC.pilot_ready(c))

    def test_two_helper_buckets_alternate_families(self):
        def sim(name, family, stars):
            spec = dict(strategy="family-config", role="sim-env", family=family, reason=f"family:{family}",
                        modes=("simulated",), stars=stars)
            if family == "gymnasium":
                spec["scan_facts"] = scan([], gym=[{"id": "G-v0", "entry_point": "g.e:Env", "file": "g/__init__.py",
                                                    "line": 1, "class_file": "g/e.py", "class_line": 3}],
                                          imports=("gymnasium",))
            else:
                spec["scan_facts"] = scan([], imports=("mujoco",), mjcf=("m/scene.xml",),
                                          mjcf_main=[{"file": "m/scene.xml", "line": 1, "kind": "scene"}])
            return (name, spec)
        specs = [sim(f"gym{i}", "gymnasium", 1000) for i in range(6)] + [sim(f"mj{i}", "mujoco", 10) for i in range(6)]
        cards, decisions, fs, stars = WaveAndRankTests.build(None, specs)
        picked = [p["package_id"] for p in TC.assign_waves(cards, decisions, fs, stars, pilot_size=4)["pilot"]]
        # the other buckets are empty, so the simulator bucket takes all four slots, one family at a time
        self.assertEqual([cards[p]["family"] for p in picked], ["gymnasium", "mujoco", "gymnasium", "mujoco"])

    def test_gym_id_templates_are_marked_in_the_hints(self):
        gym = [{"id": "FetchSlide{}-v1", "entry_point": "robo.fetch:FetchSlideEnv", "file": "robo/__init__.py",
                "line": 26, "template": True, "class_file": "robo/fetch.py", "class_line": 12}]
        f = facts("robo", scan_facts=scan([], gym=gym, imports=("gymnasium",)))
        c = card(f, decision(f, strategy="family-config", role="sim-env", family="gymnasium", reason="family:gymnasium"),
                 modes=("simulated",))
        self.assertEqual(c["hints"]["actions"],
                         ["gym env FetchSlide{}-v1 (id template, built at run time) registered at robo/__init__.py:26"])


if __name__ == "__main__":
    unittest.main()
