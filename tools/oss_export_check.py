#!/usr/bin/env python3
"""Export the open-source tree and check it.  Standard library plus ``git``.

    python3 tools/oss_export_check.py                  # export, static checks, then every suite inside the export
    python3 tools/oss_export_check.py --skip-suites    # static checks only (fast)
    python3 tools/oss_export_check.py --keep           # keep the export directory and print its path

What a clone of the repository will contain is decided by the ``.gitignore`` files (the root one is an allowlist).  This
copies the allowlisted top-level items into a temporary directory, lets ``git add -A`` apply the real ignore rules there and
keeps exactly the files git would track.  Then it asserts, on that export:

* only allowlisted top-level names exist, and the required files (licences, README, CI, ...) are present;
* no absolute home-directory path (macOS style), no CJK text outside the registry's ``x-vendor`` provenance fields and the
  files ``cjk_allowed`` names, no ``modelhardwarestandard`` outside ``domain_allowed`` (Anthropic's domain may only be cited,
  in appendix D, and spelled in ``mhs/_ids.py`` as the legacy schema prefix), no CNAME file, and the README files start with
  the non-affiliation statement;
* and, unless --skip-suites, that the suites pass *inside the export*, which is the proof that nothing depends on the private
  workspace: schema/data sync, SDK, registry (without the corpus), spec doctests and generated files, the site build and check,
  the exemplar gates (they read the upstream clones, taken from this workspace's ``labs/``/``robots/`` when present) and the
  OpenAI4S integration suite (when an OpenAI4S source checkout is found).

Exit code 0 prints ``OK``; 1 lists the problems; 2 is a usage or environment error.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REQUIRED = [
    "README.md", "LICENSE", "LICENSE-docs", "NOTICE", "SECURITY.md", "CODE_OF_CONDUCT.md", "CONTRIBUTING.md", "CHANGELOG.md",
    ".gitignore", ".github/workflows/ci.yml", "tools/oss_export_check.py", "MHS/README.md", "MHS/sdk/README.md",
    "MHS/sdk/pyproject.toml", "MHS/spec/README.md", "MHS/handoff/README.md", "MHS/drivers/README.md",
]
NON_AFFILIATION = "not affiliated with or endorsed by Anthropic"
README_FILES = ["README.md", "MHS/README.md", "MHS/sdk/README.md"]
# Files that may spell Anthropic's domain: the appendix that cites the preview, the identifier module (legacy schema prefix),
# history files that describe its removal, registry records ABOUT third-party repositories that happen to carry the name,
# and tests that assert the string is absent.
DOMAIN_ALLOWED = {"MHS/spec/appendix-d-anthropic-mhs.md", "MHS/sdk/src/mhs/_ids.py", "CHANGELOG.md", "tools/oss_export_check.py",
                  "MHS/registry/corpus.lock.jsonl", "MHS/registry/uncloned.json"}
DOMAIN_ALLOWED_PREFIXES = ("MHS/changes/", "MHS/registry/repos/", "MHS/registry/tasks/", "MHS/registry/tests/", "MHS/sdk/tests/")
# An absolute home path is allowed only where a test uses one as sample text that must be redacted.
HOME_ALLOWED = {"MHS/sdk/tests/safety/test_long_running.py"}


def cjk_allowed(rel: str) -> bool:
    """CJK text may appear only in the original-language provenance of registry records (x-vendor, handled separately), in
    the registry's own code and tests (they parse the Chinese-language source catalogue, so its words are data), and in
    the unmatched-catalogue-rows file that keeps catalogue text verbatim."""
    if rel == "MHS/registry/uncloned.json":
        return True
    if rel in ("LICENSE", "MHS/sdk/LICENSE"):
        return True  # the copyright holder in the MIT licence is also named in its original language
    return rel.startswith("MHS/registry/") and rel.endswith(".py")


_CJK_RANGES = [(0x3040, 0x30FF), (0x3400, 0x4DBF), (0x4E00, 0x9FFF), (0xAC00, 0xD7AF), (0xF900, 0xFAFF), (0x3000, 0x303F),
               (0xFF00, 0xFFEF)]
CJK = re.compile("[" + "".join(f"{chr(a)}-{chr(b)}" for a, b in _CJK_RANGES) + "]")
# A file of an upstream clone that a driver package cites (``path:LINE``): its name is an identifier, not prose, so a vendor
# manual named in its own language may be cited.  Only whole path tokens with a file extension are taken out.
CITED_PATH = re.compile(r"[^\s\"'`|(){}\[\],;]+\.(?:md|markdown|rst|txt|pdf|py|pyi|h|hpp|c|cc|cpp|json|ya?ml|toml|xml|html?|csv|ini|cfg)"
                        r"(?::[0-9][0-9,: -]*)?")


def without_cited_paths(text: str) -> str:
    return CITED_PATH.sub("", text)
HOME = "/" + "Users" + "/"  # an absolute home-directory path of the maintainer's machine
TEMP_PATHS = ("/private/" + "tmp", "/var/" + "folders", "claude-" + "501")  # scratch locations of the build machine
TEXT_LIMIT = 6_000_000


def allowlist() -> list[str]:
    names = []
    for line in (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.startswith("!/"):
            names.append(line[2:].rstrip("/"))
    return names


def run(cmd: list[str], cwd: Path, env: dict[str, str] | None = None, timeout: int = 1800) -> subprocess.CompletedProcess:
    full_env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    if env:
        full_env.update(env)
    return subprocess.run(cmd, cwd=cwd, env=full_env, capture_output=True, text=True, timeout=timeout, check=False)


def export(dest: Path) -> list[str]:
    """Copy the allowlisted items into ``dest`` and keep exactly what git would track; return the tracked paths."""
    names = allowlist()
    if not names:
        raise SystemExit("error: the root .gitignore has no '!/name' allowlist lines")
    skip = shutil.ignore_patterns("__pycache__", "*.pyc", ".DS_Store")
    for name in names + [".gitignore"]:
        src = ROOT / name
        if not src.exists():
            continue
        if src.is_dir():
            shutil.copytree(src, dest / name, ignore=skip, symlinks=False)
        else:
            shutil.copy2(src, dest / name)
    git = ["git", "-c", "core.excludesFile=/dev/null", "-c", "init.defaultBranch=main"]
    for args in (["init", "--quiet"], ["add", "-A"]):
        result = subprocess.run(git + args, cwd=dest, capture_output=True, text=True, check=False)
        if result.returncode != 0:
            raise SystemExit(f"error: git {' '.join(args)} failed in the export: {result.stderr.strip()[-300:]}")
    listed = subprocess.run(git + ["ls-files", "-z"], cwd=dest, capture_output=True, text=True, check=False).stdout
    tracked = [p for p in listed.split("\0") if p]
    keep = set(tracked)
    for path in sorted(dest.rglob("*"), key=lambda p: len(p.parts), reverse=True):
        rel = path.relative_to(dest).as_posix()
        if rel == ".git" or rel.startswith(".git/"):
            continue
        if path.is_file() or path.is_symlink():
            if rel not in keep:
                path.unlink()
        elif path.is_dir() and not any(path.iterdir()):
            path.rmdir()
    shutil.rmtree(dest / ".git")
    return sorted(keep)


def read_text(path: Path) -> str | None:
    try:
        if path.stat().st_size > TEXT_LIMIT:
            return None
        return path.read_bytes().decode("utf-8")
    except (UnicodeDecodeError, OSError):
        return None


def strip_vendor(node):
    if isinstance(node, dict):
        return {k: strip_vendor(v) for k, v in node.items() if k != "x-vendor"}
    if isinstance(node, list):
        return [strip_vendor(v) for v in node]
    return node


def static_checks(dest: Path, tracked: list[str]) -> list[str]:
    problems = []
    allowed_top = set(allowlist()) | {".gitignore"}
    for rel in tracked:
        if rel.split("/", 1)[0] not in allowed_top:
            problems.append(f"top-level name not on the allowlist: {rel}")
    for rel in REQUIRED:
        if rel not in tracked:
            problems.append(f"required file missing from the export: {rel}")
    if any(Path(rel).name == "CNAME" for rel in tracked):
        problems.append("a CNAME file is tracked (the domain is a deployment setting)")
    for rel in README_FILES:
        text = read_text(dest / rel)
        first = next((line for line in (text or "").splitlines() if line.strip()), "")
        if NON_AFFILIATION not in first:
            problems.append(f"{rel}: the first line is not the non-affiliation statement")
    pyproject = read_text(dest / "MHS/sdk/pyproject.toml") or ""
    if NON_AFFILIATION not in pyproject:
        problems.append("MHS/sdk/pyproject.toml: the description lacks the non-affiliation statement")
    absolute, domain, cjk = [], [], []
    for rel in tracked:
        path = dest / rel
        text = read_text(path)
        if text is None:
            continue
        for number, line in enumerate(text.splitlines(), 1):
            if HOME in line and rel not in HOME_ALLOWED:
                absolute.append(f"{rel}:{number}")
            elif any(marker in line for marker in TEMP_PATHS) and rel != "tools/oss_export_check.py":
                absolute.append(f"{rel}:{number}")
        if "modelhardwarestandard" in text.lower():
            if rel not in DOMAIN_ALLOWED and not rel.startswith(DOMAIN_ALLOWED_PREFIXES):
                domain.append(rel)
        if cjk_allowed(rel) or not CJK.search(text):
            continue
        if rel.startswith("MHS/drivers/") and not CJK.search(without_cited_paths(text)):
            continue
        if rel.startswith("MHS/registry/repos/") and rel.endswith(".json"):
            try:
                if not CJK.search(json.dumps(strip_vendor(json.loads(text)), ensure_ascii=False)):
                    continue
            except ValueError:
                pass
        cjk.append(rel)
    if absolute:
        problems.append(f"absolute home-directory paths in {len(absolute)} place(s), first: {', '.join(absolute[:8])}")
    if domain:
        problems.append(f"'modelhardwarestandard' outside the allowed files: {', '.join(domain[:12])}")
    if cjk:
        problems.append(f"CJK text outside x-vendor / allowed files in {len(cjk)} file(s), first: {', '.join(cjk[:8])}")
    return problems


def tail(result: subprocess.CompletedProcess, n: int = 12) -> str:
    lines = (result.stdout + result.stderr).strip().splitlines()
    return "\n    ".join(lines[-n:])


def suites(dest: Path, openai4s_src: Path | None) -> list[str]:
    problems = []
    sdk_env = {"PYTHONPATH": str(dest / "MHS/sdk/src")}

    def step(name: str, cmd: list[str], env: dict[str, str] | None = None, timeout: int = 1800) -> bool:
        print(f"  running: {name} ...", flush=True)
        try:
            result = run(cmd, dest, env, timeout)
        except subprocess.TimeoutExpired:
            problems.append(f"{name}: timed out")
            return False
        if result.returncode != 0:
            problems.append(f"{name}: exit {result.returncode}\n    {tail(result)}")
            return False
        return True

    py = sys.executable
    step("sync_data.py", [py, "MHS/sdk/tools/sync_data.py"])
    step("sync_data.py --check", [py, "MHS/sdk/tools/sync_data.py", "--check"])
    for tool in ("gen_errors.py", "gen_appendices.py", "build_applicability.py"):
        if (dest / "MHS/sdk/tools" / tool).exists():
            step(f"{tool} --check", [py, f"MHS/sdk/tools/{tool}", "--check"], sdk_env)
    if (dest / "MHS/sdk/tools/spec_doctest.py").exists():
        step("spec_doctest.py", [py, "MHS/sdk/tools/spec_doctest.py", "MHS/spec"], sdk_env)
    step("SDK tests", [py, "-m", "unittest", "discover", "-s", "MHS/sdk/tests", "-t", "MHS/sdk"], sdk_env)
    step("registry tests", [py, "-m", "unittest", "discover", "-s", "MHS/registry/tests"], sdk_env)
    step("registry build_index.py", [py, "MHS/registry/build_index.py"], sdk_env)
    step("registry validate.py --no-corpus", [py, "MHS/registry/validate.py", "--no-corpus"], sdk_env)
    site = dest.parent / (dest.name + "-site")
    base = "https://example.invalid/"
    if step("site build --release", [py, "MHS/site/build.py", "--release", "--site-url", base, "--out", str(site)], sdk_env):
        step("site check --fresh", [py, "MHS/site/check.py", "--site", str(site), "--site-url", base, "--fresh"], sdk_env)
    shutil.rmtree(site, ignore_errors=True)
    step("thermostat gate", [py, "-m", "mhs.driver", "check", "MHS/sdk/examples/thermostat", "--backend", "fake", "--no-report"], sdk_env)
    listing = dest / "MHS/drivers/EXEMPLARS.txt"
    for line in listing.read_text(encoding="utf-8").splitlines() if listing.exists() else []:
        directory = line.strip()
        if not directory:
            continue
        card = json.loads((dest / directory / "task.json").read_text(encoding="utf-8"))
        clone = ROOT / card["local_path"]
        if not clone.is_dir():
            print(f"  skipped: exemplar gate for {directory} (no clone at {clone}; use tools/fetch_clone.py)")
            continue
        extra: list[str] = []
        if any(isinstance(item, dict) and "lock" in item for item in card.get("companions") or []):
            # Fetched companion clones (work/companions, LOCK.json) do not travel with the export.
            companions = ROOT / "work" / "companions"
            if not (companions / "LOCK.json").is_file():
                print(f"  skipped: exemplar gate for {directory} (no {companions}/LOCK.json; use "
                      "tools/fetch_companions.py)")
                continue
            extra = ["--companions-root", str(companions)]
        step(f"exemplar gate {directory}", [py, "-m", "mhs.driver", "check", directory, "--backend", "fake", "--no-report",
                                            "--clone", str(clone), *extra], sdk_env)
    if openai4s_src and openai4s_src.is_dir():
        env = {"PYTHONPATH": os.pathsep.join([str(dest / "integration/openai4s"), str(dest / "MHS/sdk/src"), str(openai4s_src)])}
        step("OpenAI4S integration tests", [py, "-m", "unittest", "discover", "-s", "integration/openai4s/tests", "-t",
                                            "integration/openai4s"], env)
    else:
        print("  skipped: OpenAI4S integration tests (no OpenAI4S source checkout; pass --openai4s-src)")
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--skip-suites", action="store_true", help="static checks only")
    parser.add_argument("--keep", action="store_true", help="keep the export directory and print its path")
    parser.add_argument("--openai4s-src", type=Path, default=ROOT / "work" / "openai4s-src",
                        help="an OpenAI4S source checkout for the integration suite (default: work/openai4s-src when present)")
    args = parser.parse_args(argv)

    if shutil.which("git") is None:
        print("error: git is required", file=sys.stderr)
        return 2
    base = Path(tempfile.mkdtemp(prefix="openmhs-export-"))
    dest = base / "export"
    dest.mkdir()
    try:
        tracked = export(dest)
        print(f"exported {len(tracked)} tracked files to {dest}")
        problems = static_checks(dest, tracked)
        if not args.skip_suites:
            problems += suites(dest, args.openai4s_src)
    finally:
        if args.keep:
            print(f"export kept at {dest}")
        else:
            shutil.rmtree(base, ignore_errors=True)
    if problems:
        print(f"\n{len(problems)} problem(s):")
        for problem in problems:
            print(" -", problem)
        return 1
    print("OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
