#!/usr/bin/env python3
"""Prepare the working directory for ONE driver package.  Standard library only.

    python3 MHS/handoff/tools/prepare.py gh.owner/repo               # create MHS/drivers/<track>/<owner>__<repo>/task.json
    python3 MHS/handoff/tools/prepare.py gh.owner/repo --dry-run     # print the plan, write nothing
    python3 MHS/handoff/tools/prepare.py gh.owner/repo --sandbox     # also a private git clone + venv for running upstream code
    python3 MHS/handoff/tools/prepare.py --sync [gh.owner/repo]      # after build_registry.py: refresh task.json copies

``--sync``: ``task.json`` of a package is a byte copy of its registry card (gate G1 CARD_EDITED), so every registry
rebuild that moves a card (a new ``package_status``) leaves the packages' copies behind. ``--sync`` copies the rebuilt
card over ``task.json`` of every existing package (or the one named) and touches nothing else; ``--dry-run`` lists them.

What it does (and nothing else):

1. finds the task card MHS/registry/tasks/<track>/<owner>__<repo>.json for the package id;
2. refuses a card that is not dispatchable (see dispatch.py), unless --force;
3. creates the driver directory named by the card and copies the card there as task.json (the gate compares it with
   the registry card, so it must stay byte-identical);
4. with --sandbox: ``git clone`` of the read-only upstream clone into work/sandbox/<owner>__<repo>/src (the same pinned
   commit, never the original) and an empty venv next to it.  The gate does not need this: it parses the original
   clone with ``ast`` and never imports it.  Use the sandbox only to run an upstream simulator or the upstream's own
   tests, and install into its venv only (MHS/handoff/SANDBOX.md).

It never writes inside labs/ or robots/ and it never installs anything.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.dont_write_bytecode = True  # importing dispatch must not leave a __pycache__ in the kit
sys.path.insert(0, str(HERE))
import dispatch  # noqa: E402  (same directory)

DEFAULT_ROOT = HERE.parents[2]


def find_card(cards: list[dict], package_id: str) -> dict | None:
    for card in cards:
        if card["package_id"] == package_id:
            return card
    return None


def git(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "--no-optional-locks", *args], cwd=cwd, capture_output=True, text=True, check=False)


def plan_for(root: Path, card: dict, sandbox: bool) -> dict:
    slug = card["driver_dir"].rsplit("/", 1)[-1]
    driver_dir = root / card["driver_dir"]
    plan = {
        "package_id": card["package_id"],
        "card": card["_path"],
        "driver_dir": str(driver_dir.relative_to(root)),
        "exemplar": card.get("exemplar"),
        "clone": card["local_path"],
        "pinned_commit": card["upstream"]["commit"],
        "gate": f"PYTHONPATH=MHS/sdk/src python3 -m mhs.driver check {card['driver_dir']} --backend fake",
    }
    if sandbox:
        plan["sandbox_src"] = f"work/sandbox/{slug}/src"
        plan["sandbox_venv"] = f"work/sandbox/{slug}/venv"
    return plan


def sync_cards(root: Path, package_id: str | None, dry_run: bool) -> int:
    """Copy the registry card over ``task.json`` of every existing driver package (or of ``package_id``)."""
    slug = package_id[3:].replace("/", "__") if package_id else None
    changed: list[str] = []
    missing: list[str] = []
    for task in sorted((root / "MHS" / "drivers").glob("*/*/task.json")):
        package = task.parent
        if slug is not None and package.name != slug:
            continue
        registry = root / "MHS" / "registry" / "tasks" / package.parent.name / f"{package.name}.json"
        if not registry.is_file():
            missing.append(str(package.relative_to(root)))
        elif registry.read_bytes() != task.read_bytes():
            changed.append(str(package.relative_to(root)))
            if not dry_run:
                shutil.copyfile(registry, task)
    verb = "would refresh" if dry_run else "refreshed"
    for name in changed:
        print(f"{verb} {name}/task.json")
    for name in missing:
        print(f"error: {name} has no registry card", file=sys.stderr)
    print(f"{len(changed)} task.json {'would be refreshed' if dry_run else 'refreshed'}; {len(missing)} package(s) without a card")
    return 1 if missing else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("package_id", nargs="?", help="for example gh.tiagocoutinho/julabo (optional with --sync)")
    parser.add_argument("--sync", action="store_true",
                        help="refresh task.json of existing packages from the rebuilt registry cards; nothing else")
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT, help="repository root (default: found from this file)")
    parser.add_argument("--dry-run", action="store_true", help="print the plan and write nothing")
    parser.add_argument("--sandbox", action="store_true", help="also create work/sandbox/<id>/{src,venv}")
    parser.add_argument("--force", action="store_true", help="prepare a card that dispatch.py would not give out")
    args = parser.parse_args(argv)

    root = args.root.resolve()
    if args.sync:
        return sync_cards(root, args.package_id, args.dry_run)
    if not args.package_id:
        parser.error("a package id is required (or --sync)")
    cards = dispatch.load_cards(root)
    card = find_card(cards, args.package_id)
    if card is None:
        print(f"error: no task card for {args.package_id!r} under {root}/MHS/registry/tasks", file=sys.stderr)
        return 2
    why = dispatch.reasons_not_dispatchable(card)
    if why and not args.force:
        print(f"error: {args.package_id} is not dispatchable: {'; '.join(why)} (--force to override)", file=sys.stderr)
        return 1

    plan = plan_for(root, card, args.sandbox)
    clone = root / card["local_path"]
    if not clone.is_dir():
        print(f"error: the upstream clone {card['local_path']} does not exist", file=sys.stderr)
        return 1
    head = git("rev-parse", "HEAD", cwd=clone).stdout.strip()
    if head != card["upstream"]["commit"]:
        print(f"error: clone HEAD {head or '?'} is not the pinned commit {card['upstream']['commit']}", file=sys.stderr)
        return 1

    print(json.dumps(plan, indent=1))
    if args.dry_run:
        print("dry run: nothing written")
        return 0

    driver_dir = root / plan["driver_dir"]
    if (driver_dir / "task.json").exists() and not args.force:
        print(f"error: {plan['driver_dir']}/task.json exists already (package_status {dispatch.status_of(card)}); --force to overwrite",
              file=sys.stderr)
        return 1
    driver_dir.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(root / card["_path"], driver_dir / "task.json")
    print(f"wrote {plan['driver_dir']}/task.json")

    if args.sandbox:
        sandbox = root / "work" / "sandbox" / card["driver_dir"].rsplit("/", 1)[-1]
        src = sandbox / "src"
        if src.exists():
            print(f"sandbox exists: {src.relative_to(root)} (left as is)")
        else:
            sandbox.mkdir(parents=True, exist_ok=True)
            result = git("clone", "--quiet", "--no-hardlinks", str(clone), str(src))
            if result.returncode != 0:
                print(f"error: git clone failed: {result.stderr.strip()}", file=sys.stderr)
                return 1
            got = git("rev-parse", "HEAD", cwd=src).stdout.strip()
            if got != card["upstream"]["commit"]:
                print(f"error: the sandbox clone is at {got}, not {card['upstream']['commit']}", file=sys.stderr)
                return 1
            print(f"cloned into {src.relative_to(root)} at {got}")
        venv = sandbox / "venv"
        if not venv.exists():
            subprocess.run([sys.executable, "-m", "venv", str(venv)], check=True)
            print(f"created {venv.relative_to(root)} (nothing installed)")
    print("next: scaffold with  PYTHONPATH=MHS/sdk/src python3 -m mhs.driver new "
          f"{plan['driver_dir']} --like {plan['exemplar']} --model-id <MODEL_ID> --run-id <RUN_ID>")
    return 0


if __name__ == "__main__":
    sys.exit(main())
