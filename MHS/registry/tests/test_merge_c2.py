#!/usr/bin/env python3
"""Regression tests for the WP-10 residuals fixed when WP-10 was merged (MERGE-C2).

- Hardware first for every repo whose code drives hardware (the C0 verification's major finding: protocol
  family-configs and twins recorded as simulated only).
- Triage: AGX Dynamics is an external engine; committed installers plus a file-host download link quarantine.
- Cards: camelCase getters and setters, motor ``control_*`` commands, reference setters, README GPU
  prerequisites and asset downloads.
- Curated data: no false partner attribution, the teaching plugins are skipped, the julabo siblings are
  direct drivers; the README's spot-check description is derived from tasks/SPOTCHECK.md.

Reads only files under MHS/ (works in a copy of MHS/ without the corpus).
"""
from __future__ import annotations

import glob
import json
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
REG = os.path.abspath(os.path.join(HERE, ".."))
MHS = os.path.abspath(os.path.join(REG, ".."))
sys.path.insert(0, REG)
sys.path.insert(0, os.path.join(MHS, "sdk", "src"))
sys.path.insert(0, HERE)

import build_registry as BR  # noqa: E402
import docs as DOCS  # noqa: E402
import source_scan as SS  # noqa: E402
import taskcards as TC  # noqa: E402
import triage as T  # noqa: E402
import validate as V  # noqa: E402
from test_triage import decide, entry_class, facts  # noqa: E402


def decision(strategy="family-config", role="twin-candidate", family="scpi", rule=9):
    return T.Decision(package_id="gh.acme/gizmo", strategy=strategy, role=role, reason_code=f"family:{family}",
                      rule=rule, family=family)


def record(modes=("simulated",), tier="B"):
    return {"tier": tier, "modes": list(modes)}


VISA_CLASS = entry_class(transport=("pyvisa",), symbol="pkg.connection:VisaConnection")
SIM_ROLE = {"category": "设备后端", "role": "直接模拟后端"}   # catalogue: device backend / direct simulation backend


class HardwareFirstTests(unittest.TestCase):
    def test_protocol_twin_with_a_hardware_transport_is_hardware_first(self):
        for family in ("scpi", "serial", "tag-bridge", "pymmcore-plus", "pylabrobot", "ros", None):
            f = facts(entry=VISA_CLASS, **SIM_ROLE)
            strategy = "untriaged" if family is None else "family-config"
            modes = BR.final_modes(record(), decision(strategy=strategy, family=family), f, None)
            self.assertEqual(modes, ["hardware", "simulated"], family)

    def test_simulator_family_twin_stays_simulated(self):
        for family in ("gymnasium", "mujoco"):
            f = facts(entry=VISA_CLASS, **SIM_ROLE)
            self.assertEqual(BR.final_modes(record(), decision(family=family), f, None), ["simulated"], family)

    def test_twin_without_hardware_code_stays_simulated(self):
        f = facts(entry=entry_class(transport=("socket",)), **SIM_ROLE)
        self.assertEqual(BR.final_modes(record(), decision(), f, None), ["simulated"])

    def test_recon_card_of_hardware_code_is_hardware_first(self):
        f = facts(entry=entry_class(transport=("serial",), symbol="pkg.servo:ServoController"))
        modes = BR.final_modes(record(["simulated"]), decision("untriaged", "not-device", None, 11), f, None)
        self.assertEqual(modes, ["hardware", "simulated"])

    def test_simulation_env_class_over_com_is_not_hardware_evidence(self):
        env = entry_class(transport=("comtypes",), symbol="Env.DC_gym:DC_Gym")
        simulator = entry_class(transport=("comtypes",), symbol="Env.DC_class:SimulatorDC")
        f = facts(entries=[env, simulator])
        self.assertIsNone(BR.hardware_evidence(f))
        modes = BR.final_modes(record(["simulated"]), decision("untriaged", "not-device", None, 11), f, None)
        self.assertEqual(modes, ["simulated"])

    def test_sim_env_role_stays_simulated(self):
        f = facts(entry=VISA_CLASS)
        modes = BR.final_modes(record(), decision("family-config", "sim-env", "gymnasium"), f, None)
        self.assertEqual(modes, ["simulated"])

    def test_validate_flags_a_simulated_only_record_with_hardware_evidence(self):
        doc = {"modes": ["simulated"], "integration": {"role": "twin-candidate", "strategy": "family-config"},
               "x-vendor": {"triage": {"family": "scpi", "hardware_transport":
                                       "class pkg:Visa uses the hardware transport pyvisa"}, "classification": {}}}
        self.assertTrue(V.check_hardware_evidence(doc))
        doc["modes"] = ["hardware", "simulated"]
        self.assertEqual(V.check_hardware_evidence(doc), [])
        doc["modes"] = ["simulated"]
        doc["x-vendor"]["triage"]["family"] = "mujoco"
        self.assertEqual(V.check_hardware_evidence(doc), [])

    def test_shipped_records_list_hardware_first_for_hardware_code(self):
        records = {}
        for path in glob.glob(os.path.join(REG, "repos", "*", "*.json")):
            with open(path, encoding="utf-8") as fh:
                doc = json.load(fh)
            records[doc["package_id"]] = doc
        bad = [(pid, V.check_hardware_evidence(doc)) for pid, doc in records.items() if V.check_hardware_evidence(doc)]
        self.assertEqual(bad[:3], [])
        cards = TC.load_cards()
        for pid in ("gh.little-did-i-know/scpi-instrument-control", "gh.tiagocoutinho/cryocon",
                    "gh.tiagocoutinho/gepace", "gh.tiagocoutinho/vacuubrand", "gh.tiagocoutinho/xia-pfcu",
                    "gh.lewbert/talos-2d-transfer", "gh.tetheria/aero-hand-open"):
            # (gh.roversx/universal-robot-mcp was one too until recon wave A made it a reference: no modes)
            doc = records[pid]
            self.assertEqual(doc["modes"][0], "hardware", pid)
            self.assertFalse(doc["hardware_free"] and doc["modes"] == ["simulated"], pid)
            plan = doc["x-vendor"]["device_plan"]
            self.assertEqual(plan[0]["mode"], "hardware", pid)
            self.assertEqual(cards[pid]["safety"]["expected_mode"], "hardware", pid)


class HardwareFirstReconTests(unittest.TestCase):
    """MERGE-C2 fix: a sim-env recon card whose code drives hardware was simulated only (openwbt, furniture-bench)."""

    def test_sim_env_recon_card_of_hardware_code_is_hardware_first(self):
        f = facts(entry=entry_class(transport=("serial",), symbol="deploy.controllers.handle:UsbHandle"))
        modes = BR.final_modes(record(["simulated"]), decision("untriaged", "sim-env", None, 11), f, None)
        self.assertEqual(modes, ["hardware", "simulated"])
        # a decided simulator family-config keeps the simulator as its driver
        modes = BR.final_modes(record(["simulated"]), decision("family-config", "sim-env", "gymnasium"), f, None)
        self.assertEqual(modes, ["simulated"])

    def test_validate_flags_a_simulated_only_sim_env_recon_card(self):
        doc = {"modes": ["simulated"], "integration": {"role": "sim-env", "strategy": "untriaged"},
               "x-vendor": {"triage": {"family": None, "hardware_transport":
                                       "class pkg:Handle uses the hardware transport serial"}, "classification": {}}}
        self.assertTrue(V.check_hardware_evidence(doc))
        doc["integration"]["strategy"] = "family-config"
        self.assertEqual(V.check_hardware_evidence(doc), [])

    def test_the_shipped_sim_env_recon_cards_of_hardware_code_were_decided_by_recon(self):
        cards = TC.load_cards()
        # These were the shipped hardware-first recon cards (expected_mode hardware, a mode recon) until recon wave B
        # decided them (MHS/changes/RECON-B.md); no untriaged card is left, so the two tests above carry the rule.
        # (gh.k4zuki/pipico-micropython-scpi was one too until recon wave A made it a skip: instrument-side firmware)
        decided = {"gh.galaxygeneralrobotics/openwbt": ("reference", "host"),
                   "gh.clvrai/furniture-bench": ("family-config", "sim-env"),
                   "gh.generalroboticslab/dukehumanoidv1": ("reference", "host")}
        for pid, shape in decided.items():
            card = cards[pid]
            self.assertEqual((card["decision"], card["role"]), shape, pid)
            self.assertEqual(card["reason_code"], "override:recon", pid)
            self.assertNotIn("mode", card["needs_recon"], pid)
        # the gymnasium family-configs with real-robot code stay simulated (a documented known limit)
        self.assertEqual(cards["gh.google-research/robel"]["safety"]["expected_mode"], "simulated")
        self.assertNotIn("mode", cards["gh.google-research/robel"]["needs_recon"])


def ranked(classes, family="python-object"):
    return TC.ranked_classes(facts(entries=classes), family)


def device_class(symbol, file, methods=("get_temperature", "set_setpoint", "start"), members=(), bases=(), score=12):
    return {"symbol": symbol, "file": file, "line": 3, "score": score, "bases": list(bases), "methods": list(methods),
            "api_methods": list(methods), "members": list(members), "api": len(methods), "exported": False,
            "async": False, "transport": ["serial"]}


class CardRankingTests(unittest.TestCase):
    """MERGE-C2 fix: the 10b SPOTCHECK and julabo-sibling hint minors."""

    def test_tango_server_members_are_not_hints_of_the_core_class(self):
        core = device_class("cryocon.cryocon:CryoCon", "cryocon/cryocon.py", methods=("get_temperature",),
                            score=14)
        server = device_class("cryocon.tango.server.cryocon:CryoCon", "cryocon/tango/server/cryocon.py",
                              methods=("read_attr_hardware", "on", "off"), members=("ReadValidityPeriod",))
        classes = ranked([server, core])
        self.assertEqual([c["symbol"] for c in classes][0], "cryocon.cryocon:CryoCon")
        hints, _caps = TC.device_hints(facts(entries=[server, core]), "labs", classes)
        text = " ".join(hints["reads"] + hints["writes"] + hints["actions"])
        self.assertIn("CryoCon.get_temperature", text)
        for member in ("read_attr_hardware", "ReadValidityPeriod", "CryoCon.on"):
            self.assertNotIn(member, text)

    def test_pymodaq_plugins_rank_below_their_hardware_wrapper(self):
        plugin = device_class("pkg.daq_move_plugins.daq_move_PI:DAQ_Move_PI", "src/pkg/daq_move_plugins/daq_move_PI.py",
                              methods=("move_abs", "move_home", "stop_motion"), score=15)
        wrapper = device_class("pkg.hardware.pi_wrapper:PIWrapper", "src/pkg/hardware/pi_wrapper.py",
                               methods=("get_axis_limits", "read_voltage"), score=12)
        classes = ranked([plugin, wrapper])
        self.assertEqual(classes[0]["symbol"], "pkg.hardware.pi_wrapper:PIWrapper")
        hints, caps = TC.device_hints(facts(entries=[plugin, wrapper]), "labs", classes)
        self.assertFalse(any(h.startswith("DAQ_Move_PI.") for h in hints["actions"] + hints["reads"]), hints)
        self.assertFalse(any(c.startswith("cap.motion.") for c in caps), caps)
        # with nothing else ranked the plugin stays the entry and the source of hints
        alone = ranked([plugin])
        self.assertEqual(alone[0]["symbol"], plugin["symbol"])
        self.assertTrue(TC.device_hints(facts(entries=[plugin]), "labs", alone)[0]["actions"])

    def test_qt_wrapper_ranks_below_the_device_class_and_gives_no_hints(self):
        qt = device_class("Alia_qdev:Alia_qdev", "Alia_qdev.py", methods=("turn_on", "set_ref_freq"),
                          members=("signal_ref_freq_is_set",), bases=("QDeviceIO",), score=16)
        serial = device_class("Alia_protocol_serial:Alia", "Alia_protocol_serial.py",
                              methods=("turn_on", "query_ref", "set_ref"), score=13)
        classes = ranked([qt, serial])
        self.assertEqual(classes[0]["symbol"], "Alia_protocol_serial:Alia")
        hints, _caps = TC.device_hints(facts(entries=[qt, serial]), "labs", classes)
        self.assertFalse(any("signal_" in h or h.startswith("Alia_qdev.") for h in hints["reads"] + hints["writes"]))
        self.assertIsNone(TC._QT_BASE.match("QDac2"))   # an instrument named Q... is not a Qt base

    def test_debug_scripts_are_never_entries(self):
        real = device_class("Alia_protocol_serial:Alia", "Alia_protocol_serial.py")
        debug = device_class("debug_Alia_qdev:Alia_qdev", "debug_Alia_qdev.py", score=20)
        self.assertEqual([c["symbol"] for c in ranked([debug, real])], ["Alia_protocol_serial:Alia"])

    def test_vendored_rl_libraries_rank_below_the_package(self):
        vendored = device_class("stable_baselines3.common.vec_env.vec_monitor:VecMonitor",
                                "stable_baselines3/common/vec_env/vec_monitor.py", score=12)
        own = device_class("dexart.env.rl_env:AllegroRelocateEnv", "dexart/env/rl_env.py", score=10)
        self.assertEqual(ranked([vendored, own])[0]["symbol"], own["symbol"])


class TriageTests(unittest.TestCase):
    def test_agx_is_an_external_engine(self):
        f = facts("gym-agx", imports={"gymnasium", "agx"}, gym_ids=["BendWire-v0"])
        d = decide(f)
        self.assertNotEqual(d.family, "gymnasium")
        self.assertIn("agx", TC.EXTERNAL_ENGINE_IMPORTS)

    def test_committed_installers_with_a_file_host_link_quarantine(self):
        readme = {"download_cta": ["http://gestyy.com/abc", "https://mega.nz/file/x"], "lure_words": []}
        f = facts("opc-tools", python=12, readme=readme)
        f.scan["counts"]["installers"] = 15
        self.assertTrue(T.lure_signals(f))
        self.assertTrue(decide(f).quarantine)

    def test_installers_with_the_owners_documentation_page_do_not_quarantine(self):
        readme = {"download_cta": ["https://acme.github.io/sim/install_precompiled"], "lure_words": []}
        f = facts("sim", python=120, readme=readme)
        f.scan["counts"]["installers"] = 3
        self.assertEqual(T.lure_signals(f), [])

    def test_link_shorteners_are_lure_hosts(self):
        facts_ = SS.readme_facts("Get the tools: [Download here](http://gestyy.com/etVOqH)", owner="acme")
        self.assertEqual(facts_["download_cta"], ["http://gestyy.com/etVOqH"])

    def test_summary_names_the_decision_level_count(self):
        summary = T.summarize(T.triage([facts("a", imports={"pyvisa"})]))
        self.assertIn("dispatchable_decisions", summary)
        self.assertNotIn("dispatchable_now", summary)
        self.assertIn("authoritative", T.format_summary(summary))


class CardHintTests(unittest.TestCase):
    def test_camel_case_getters_and_setters(self):
        self.assertEqual(TC.method_kind("getStartSpeed"), "read")
        self.assertEqual(TC.method_kind("getAIN"), "read")
        self.assertEqual(TC.method_kind("isBusy"), "read")
        self.assertEqual(TC.method_kind("setStartSpeed"), "write")
        self.assertEqual(TC.class_for("getTemperature", "read", "labs", set()), "cap.measure.temperature.v1")
        self.assertEqual(TC.class_for("setStartSpeed", "write", "labs", set()), "cap.device.configure.v1")

    def test_motor_control_commands_are_motion(self):
        self.assertEqual(TC.method_kind("controlMIT"), "action")
        self.assertEqual(TC.class_for("controlMIT", "action", "robots", set()), "cap.motion.joint_position.v1")
        self.assertEqual(TC.class_for("control_Pos_Vel", "action", "robots", set()), "cap.motion.joint_position.v1")
        self.assertEqual(TC.class_for("control_Vel", "action", "robots", set()), "cap.motion.joint_velocity.v1")
        # choosing a control mode is configuration, not a motion command
        self.assertEqual(TC.class_for("set_pos_control", "write", "robots", set()), "cap.device.configure.v1")

    def test_reference_setters_are_configuration(self):
        self.assertEqual(TC.class_for("set_zero_position", "write", "robots", set()), "cap.device.configure.v1")
        self.assertEqual(TC.class_for("setHomePosition", "write", "robots", set()), "cap.device.configure.v1")
        self.assertEqual(TC.class_for("set_position", "write", "robots", set()), "cap.motion.cartesian_pose.v1")

    def test_readme_gpu_prerequisites(self):
        positive = ["**Prerequisites:** Linux + CUDA GPU", "SAPIEN requires a GPU to run", "### Prerequisites (GPU)",
                    "- An NVIDIA GPU (ideally RTX)", "you only need to run a few pip installs and setup Vulkan"]
        negative = ["You can optionally use a CUDA GPU", "runs on a single RTX 2080 CUDA GPU at 50 frames per second",
                    "increase the GPU memory split to 256Mb", "- CUDA-compatible GPU (recommended for evaluation)",
                    "Training requires an NVIDIA GPU", "report the training device (CUDA GPU / VRAM)"]
        for text in positive:
            self.assertTrue(SS.readme_gpu_lines(text), text)
        for text in negative:
            self.assertEqual(SS.readme_gpu_lines(text), [], text)
        f = facts("sim", readme={"gpu_required": ["SAPIEN requires a GPU to run"]})
        self.assertTrue(TC.needs_gpu(f, ""))

    def test_readme_asset_downloads(self):
        hit = SS.readme_artifact_downloads(
            "Download and extract assets: gdown https://drive.google.com/file/d/1Zv/ && unzip robotwin_models.zip")
        self.assertTrue(hit)
        self.assertTrue(SS.readme_artifact_downloads("Assets: https://huggingface.co/datasets/acme/garment_assets"))
        self.assertTrue(SS.readme_artifact_downloads("wget https://storage.example/ravens-assets/kits.zip"))
        for text in ("Datasets: https://huggingface.co/datasets/acme/demos",
                     '<img src="https://drive.google.com/uc?export=view&id=1">',
                     "wget https://github.com/acme/tool/archive/v1.0.tar.gz", "Download the dataset from here"):
            self.assertEqual(SS.readme_artifact_downloads(text), [], text)


class CuratedDataTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.overrides = {}
        for path in glob.glob(os.path.join(REG, "overrides", "*.json")):
            with open(path, encoding="utf-8") as fh:
                for item in json.load(fh)["overrides"]:
                    cls.overrides[item["package_id"]] = item

    def test_pycont_has_no_partner_attribution(self):
        item = self.overrides["gh.croningp/pycont"]
        self.assertNotIn("partner", item)
        self.assertNotIn("Tecan", item["justification"])
        self.assertIn("Tricontinent", item["justification"])

    def test_teaching_plugins_are_skipped(self):
        self.assertEqual(self.overrides["gh.pymodaq/pymodaq_plugins_teaching"]["strategy"], "skip")

    def test_julabo_siblings_are_direct_drivers(self):
        cards = TC.load_cards()
        for repo in ("cryocon", "gepace", "vacuubrand", "xia-pfcu"):
            pid = f"gh.tiagocoutinho/{repo}"
            self.assertEqual(self.overrides[pid]["strategy"], "direct-driver", pid)
            card = cards[pid]
            self.assertEqual((card["decision"], card["family"]), ("direct-driver", "python-object"), pid)
            self.assertNotIn(".tango.", card["entry_symbols"][0]["symbol"], pid)

    def test_readme_spotcheck_description_matches_the_file(self):
        with open(os.path.join(REG, "README.md"), encoding="utf-8") as fh:
            readme = fh.read()
        self.assertIn(DOCS.spotcheck_summary(), readme)
        self.assertNotIn("140 random cards in four rounds", readme)

    def test_short_pilot_bucket_states_its_shortfall(self):
        with open(TC.PILOT_PATH, encoding="utf-8") as fh:
            doc = json.load(fh)
        share = doc["count"] // len(doc["buckets"])
        for name, bucket in doc["buckets"].items():
            self.assertEqual("shortfall" in bucket, bucket["count"] < share, name)


if __name__ == "__main__":
    unittest.main()
