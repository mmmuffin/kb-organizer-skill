#!/usr/bin/env python3
"""Bootstrap runtime dependencies for knowledge-base-organizer."""

from __future__ import annotations

import argparse
import platform
import shutil
import subprocess
import sys
from dataclasses import dataclass

CORE_PACKAGES = ["pandas", "requests", "beautifulsoup4", "pillow", "pypdf", "openpyxl", "lxml"]
OCR_PACKAGES = ["paddleocr"]
PADDLE_CPU_INDEX = "https://www.paddlepaddle.org.cn/packages/stable/cpu/"


@dataclass
class InstallPlan:
    profile: str
    python_commands: list[list[str]]
    system_commands: list[list[str]]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", choices=["none", "mobile", "server"], default="mobile")
    parser.add_argument("--yes", action="store_true", help="Execute without interactive confirmation")
    parser.add_argument("--with-tesseract", action="store_true", help="Also install tesseract CLI as fallback OCR")
    parser.add_argument("--print-plan", action="store_true", help="Print the planned commands and exit")
    parser.add_argument("--python", default=sys.executable, help="Python interpreter to use for pip installs")
    return parser.parse_args()


def build_plan(args: argparse.Namespace) -> InstallPlan:
    python_commands: list[list[str]] = [
        [args.python, "-m", "pip", "install", *CORE_PACKAGES],
    ]
    if args.profile in {"mobile", "server"}:
        python_commands.append([args.python, "-m", "pip", "install", "paddlepaddle", "-i", PADDLE_CPU_INDEX])
        python_commands.append([args.python, "-m", "pip", "install", *OCR_PACKAGES])

    system_commands: list[list[str]] = []
    if args.profile in {"mobile", "server"}:
        if shutil.which("brew"):
            system_commands.append(["brew", "install", "poppler"])
            if args.with_tesseract:
                system_commands.append(["brew", "install", "tesseract"])
        elif shutil.which("apt-get"):
            system_commands.append(["sudo", "apt-get", "update"])
            system_commands.append(["sudo", "apt-get", "install", "-y", "poppler-utils"])
            if args.with_tesseract:
                system_commands.append(["sudo", "apt-get", "install", "-y", "tesseract-ocr"])

    return InstallPlan(profile=args.profile, python_commands=python_commands, system_commands=system_commands)


def print_plan(plan: InstallPlan) -> None:
    print(f"# Bootstrap Plan ({plan.profile})")
    print("")
    print(f"Platform: {platform.system()} {platform.release()}")
    print("")
    print("## Python")
    for command in plan.python_commands:
        print("- " + " ".join(command))
    print("")
    print("## System")
    if plan.system_commands:
        for command in plan.system_commands:
            print("- " + " ".join(command))
    else:
        print("- No system package commands required for this profile.")


def confirm_execution() -> bool:
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        return False
    reply = input("Execute these commands now? [y/N] ").strip().lower()
    return reply in {"y", "yes"}


def run_commands(commands: list[list[str]]) -> None:
    for command in commands:
        print("+ " + " ".join(command))
        completed = subprocess.run(command, check=False)
        if completed.returncode != 0:
            raise SystemExit(completed.returncode)


def main() -> None:
    args = parse_args()
    plan = build_plan(args)
    print_plan(plan)

    if args.print_plan:
        return

    if not args.yes and not confirm_execution():
        raise SystemExit("Cancelled.")

    run_commands(plan.python_commands)
    run_commands(plan.system_commands)
    print("")
    print("Bootstrap completed. Run `python3 scripts/organize_kb.py --check-deps` to verify capabilities.")


if __name__ == "__main__":
    main()
