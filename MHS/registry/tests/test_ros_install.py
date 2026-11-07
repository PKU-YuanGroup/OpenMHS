"""Root ROS recipes require pinned static evidence, never executing setup/build code."""
from __future__ import annotations
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

REG = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REG))
sys.path.insert(0, str(REG / "tests"))
import ros_build as R
import source_scan as S
import taskcards as TC
import triage as T
from test_taskcards import facts, scan, entry, card, decision
from mhs.driver.upstream import _git_env


def git(root, *args):
    env = _git_env()
    env.update(GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull)
    done = subprocess.run(["git", "--no-optional-locks", "-C", str(root),
                           "-c", "user.name=install-test", "-c", "user.email=install-test@invalid",
                           "-c", "commit.gpgsign=false", *args], capture_output=True, text=True,
                          timeout=30, env=env, check=True, stdin=subprocess.DEVNULL)
    return done.stdout.strip()


class RosInstallTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def write(self, name, text):
        target = self.root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text)

    def recipe(self, evidence=None):
        data = scan([entry()], root_files=tuple(p.name for p in self.root.iterdir() if p.is_file()))
        data["install"]["ros_build"] = evidence if evidence is not None else R.scan_ros_build(self.root)
        f = facts(scan_facts=data)
        return TC.install_block(f, False, "linux"), card(f, decision(f))

    def test_catkin_setup_is_workspace_build_not_pip(self):
        self.write("package.xml", "<package>\n<buildtool_depend>catkin</buildtool_depend>\n</package>")
        self.write("setup.py", "from catkin_pkg.python_setup import generate_distutils_setup\n")
        result = R.scan_ros_build(self.root)
        self.assertEqual(result["status"], "catkin")
        self.assertEqual(result["evidence"][0]["line"], 2)
        install, _ = self.recipe(result)
        self.assertEqual(install["commands"], ["catkin_make"])
        self.assertIn("workspace root", " ".join(install["system_deps"]))
        self.assertFalse(any(word in str(result) for word in ("Noetic", "Humble", "ROS 1", "ROS 2")))

    def test_ament_cmake_and_python_explicit_types(self):
        for marker in ("ament_cmake", "ament_python"):
            with self.subTest(marker=marker):
                self.write("package.xml", f"<package><export><build_type>{marker}</build_type></export></package>")
                self.write("setup.py", "from setuptools import setup\nsetup()\n")
                result = R.scan_ros_build(self.root)
                self.assertEqual(result["status"], "ament")
                self.assertEqual(self.recipe(result)[0]["commands"], ["colcon build"])

    def test_bare_package_xml_is_not_colcon_or_pip_evidence(self):
        self.write("package.xml", "<package/>")
        self.write("setup.py", "from setuptools import setup\n")
        install, generated = self.recipe()
        self.assertEqual(install["commands"], [])
        self.assertIn("install", generated["needs_recon"])

    def test_unconditional_multiline_cmake_marker(self):
        self.write("package.xml", "<package/>")
        self.write("CMakeLists.txt", "find_package(\n catkin REQUIRED\n COMPONENTS rospy\n)\ncatkin_package()\n")
        self.assertEqual(R.scan_ros_build(self.root)["status"], "catkin")

    def test_comments_strings_and_docstrings_do_not_prove_build_tool(self):
        self.write("package.xml", "<package><!-- <buildtool_depend>catkin</buildtool_depend> --></package>")
        self.write("CMakeLists.txt", '# find_package(catkin)\nmessage("ament_package()")\n#[[\ncatkin_package()\n]]\nset(TEXT [=[\ntext()\nfind_package(catkin)\n]=])\n')
        self.write("setup.py", '"""from catkin_pkg.python_setup import generate_distutils_setup"""\n')
        result = R.scan_ros_build(self.root)
        self.assertEqual((result["status"], result["evidence"]), ("unknown", []))

    def test_conditional_xml_cmake_and_setup_are_unresolved(self):
        cases = [
            ("package.xml", '<package><buildtool_depend condition="$ROS_VERSION == 1">catkin</buildtool_depend></package>'),
            ("CMakeLists.txt", "if(ROS_VERSION EQUAL 1)\nfind_package(catkin REQUIRED)\nendif()\n"),
            ("setup.py", "if False:\n from catkin_pkg.python_setup import generate_distutils_setup\n"),
        ]
        for name, text in cases:
            with self.subTest(name=name):
                for existing in self.root.iterdir():
                    existing.unlink()
                self.write("package.xml", "<package/>")
                self.write(name, text)
                result = R.scan_ros_build(self.root)
                self.assertEqual(result["status"], "unknown")
                self.assertTrue(all(row["conditional"] for row in result["evidence"]))
                self.assertEqual(self.recipe(result)[0]["commands"], [])

    def test_mixed_families_are_not_guessed(self):
        self.write("package.xml", "<package><buildtool_depend>catkin</buildtool_depend></package>")
        self.write("CMakeLists.txt", "find_package(ament_cmake REQUIRED)\nament_package()\n")
        result = R.scan_ros_build(self.root)
        self.assertEqual(result["status"], "ambiguous")
        self.assertEqual(self.recipe(result)[0]["commands"], [])

    def test_nested_ros_package_does_not_change_root_python_recipe(self):
        self.write("child/package.xml", "<package><buildtool_depend>catkin</buildtool_depend></package>")
        self.write("setup.py", "from setuptools import setup\n")
        result = R.scan_ros_build(self.root)
        self.assertEqual(result["status"], "none")
        self.assertEqual(self.recipe(result)[0]["commands"], ["pip install ."])

    def test_catkin_setup_without_package_xml_requires_recon(self):
        self.write("setup.py", "from catkin_pkg.python_setup import generate_distutils_setup\n")
        self.assertEqual(R.scan_ros_build(self.root)["status"], "unknown")
        self.assertEqual(self.recipe()[0]["commands"], [])

    def test_malformed_or_entity_xml_has_no_recipe(self):
        for text in ("<package>", '<!DOCTYPE package [<!ENTITY x "catkin">]><package><buildtool_depend>&x;</buildtool_depend></package>'):
            with self.subTest(text=text):
                self.write("package.xml", text)
                self.write("CMakeLists.txt", "find_package(catkin REQUIRED)\n")
                self.assertEqual(R.scan_ros_build(self.root)["status"], "unknown")
                self.assertEqual(self.recipe()[0]["commands"], [])

    def test_setup_sentinel_is_never_executed(self):
        self.write("package.xml", "<package><buildtool_depend>catkin</buildtool_depend></package>")
        self.write("setup.py", "from pathlib import Path\nPath(__file__).with_name('EXECUTED').write_text('bad')\nfrom catkin_pkg.python_setup import generate_distutils_setup\n")
        result = S.scan_repo(str(self.root))
        self.assertEqual(result["install"]["ros_build"]["status"], "catkin")
        self.assertFalse((self.root / "EXECUTED").exists())

    def test_pinned_commit_wins_over_modified_and_missing_checkout_files(self):
        self.write("package.xml", "<package><buildtool_depend>catkin</buildtool_depend></package>")
        self.write("setup.py", "from catkin_pkg.python_setup import generate_distutils_setup\n")
        git(self.root, "init", "-q"); git(self.root, "add", "."); git(self.root, "commit", "-qm", "catkin")
        pin = git(self.root, "rev-parse", "HEAD")
        self.write("package.xml", "<package><buildtool_depend>ament_cmake</buildtool_depend></package>")
        (self.root / "setup.py").unlink()
        result = S.scan_repo(str(self.root), commit=pin)["install"]["ros_build"]
        self.assertEqual((result["status"], result["commit"], result["source"]), ("catkin", pin, "pinned"))
        self.assertIn("setup.py", result["root_files"])
        self.assertEqual(self.recipe(result)[0]["commands"], ["catkin_make"])

    def test_missing_pin_never_falls_back_to_catkin_checkout(self):
        self.write("package.xml", "<package><buildtool_depend>catkin</buildtool_depend></package>")
        result = R.scan_ros_build(self.root, "1" * 40)
        self.assertEqual(result["status"], "unavailable")
        self.assertEqual(self.recipe(result)[0]["commands"], [])

    def test_symlink_is_not_regular_build_evidence(self):
        self.write("real.xml", "<package><buildtool_depend>catkin</buildtool_depend></package>")
        (self.root / "package.xml").symlink_to("real.xml")
        self.assertEqual(R.scan_ros_build(self.root)["status"], "unavailable")
        git(self.root, "init", "-q"); git(self.root, "add", "."); git(self.root, "commit", "-qm", "symlink")
        pin = git(self.root, "rev-parse", "HEAD")
        self.assertEqual(R.scan_ros_build(self.root, pin)["status"], "unavailable")

    def test_gitlink_is_not_regular_build_evidence(self):
        self.write("file", "first")
        git(self.root, "init", "-q"); git(self.root, "add", "."); git(self.root, "commit", "-qm", "first")
        child = git(self.root, "rev-parse", "HEAD")
        git(self.root, "update-index", "--add", "--cacheinfo", f"160000,{child},package.xml")
        git(self.root, "commit", "-qm", "gitlink")
        result = R.scan_ros_build(self.root, git(self.root, "rev-parse", "HEAD"))
        self.assertEqual(result["status"], "unavailable")

    def test_oversized_build_file_does_not_gain_evidence_from_truncated_head(self):
        self.write("package.xml", "<package><buildtool_depend>catkin</buildtool_depend></package>" + " " * R.MAX_BYTES)
        self.assertEqual(R.scan_ros_build(self.root)["status"], "unavailable")

    def test_scan_corpus_passes_pin_to_root_evidence(self):
        clone = self.root / "robots/acme/example"
        clone.mkdir(parents=True)
        (clone / "package.xml").write_text("<package><buildtool_depend>catkin</buildtool_depend></package>")
        git(clone, "init", "-q"); git(clone, "add", "."); git(clone, "commit", "-qm", "catkin")
        pin = git(clone, "rev-parse", "HEAD")
        (clone / "package.xml").write_text("<package><buildtool_depend>ament_cmake</buildtool_depend></package>")
        result = T.scan_corpus(str(self.root), ["robots/acme/example"], commits={"robots/acme/example": pin})
        self.assertEqual(result["robots/acme/example"]["install"]["ros_build"]["status"], "catkin")


if __name__ == "__main__":
    unittest.main()
