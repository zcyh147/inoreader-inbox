#!/usr/bin/env python3
"""Launcher that runs skill scripts inside the skill-local virtual environment."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path


def venv_python(skill_dir: Path) -> Path:
    if os.name == "nt":
        return skill_dir / ".venv" / "Scripts" / "python.exe"
    return skill_dir / ".venv" / "bin" / "python"


def ensure_venv(skill_dir: Path) -> Path:
    python = venv_python(skill_dir)
    setup_script = skill_dir / "scripts" / "setup_environment.py"
    if not python.exists():
        print("First run: setting up skill virtual environment...")
    result = subprocess.run([sys.executable, str(setup_script)])
    if result.returncode != 0:
        raise SystemExit(result.returncode)
    return python


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Set up/check the virtual environment and exit")
    parser.add_argument("script", nargs="?", help="Script name under scripts/")
    parser.add_argument("args", nargs=argparse.REMAINDER)
    ns = parser.parse_args()

    skill_dir = Path(__file__).resolve().parent.parent
    python = ensure_venv(skill_dir)
    if ns.check:
        return 0

    if not ns.script:
        parser.error("script is required unless --check is used")

    script_name = ns.script[8:] if ns.script.startswith("scripts/") else ns.script
    if not script_name.endswith(".py"):
        script_name += ".py"
    script_path = skill_dir / "scripts" / script_name
    if not script_path.exists():
        raise SystemExit(f"Script not found: {script_path}")

    try:
        completed = subprocess.run([str(python), str(script_path), *ns.args])
    except KeyboardInterrupt:
        return 130
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())

