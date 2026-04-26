#!/usr/bin/env python3
"""Create and maintain the skill-local Python virtual environment."""

from __future__ import annotations

import hashlib
import os
import subprocess
import sys
import venv
from pathlib import Path


class SkillEnvironment:
    def __init__(self) -> None:
        self.skill_dir = Path(__file__).resolve().parent.parent
        self.venv_dir = self.skill_dir / ".venv"
        self.requirements_file = self.skill_dir / "requirements.txt"
        self.config_dir = self.skill_dir / "config"
        self.stamp_file = self.venv_dir / ".requirements.sha256"
        if os.name == "nt":
            self.python = self.venv_dir / "Scripts" / "python.exe"
            self.pip = self.venv_dir / "Scripts" / "pip.exe"
        else:
            self.python = self.venv_dir / "bin" / "python"
            self.pip = self.venv_dir / "bin" / "pip"

    def ensure(self) -> bool:
        self.config_dir.mkdir(parents=True, exist_ok=True)
        created_venv = False
        if not self.python.exists():
            print(f"Creating virtual environment: {self.venv_dir}")
            venv.create(self.venv_dir, with_pip=True)
            created_venv = True

        if created_venv or self.requirements_changed():
            if self.requirements_have_entries():
                print("Installing skill dependencies...")
                subprocess.run([str(self.python), "-m", "pip", "install", "--upgrade", "pip"], check=True)
                subprocess.run([str(self.python), "-m", "pip", "install", "-r", str(self.requirements_file)], check=True)
            self.stamp_file.write_text(self.requirements_hash(), encoding="utf-8")

        return self.python.exists()

    def requirements_hash(self) -> str:
        if not self.requirements_file.exists():
            return ""
        return hashlib.sha256(self.requirements_file.read_bytes()).hexdigest()

    def requirements_changed(self) -> bool:
        current = self.requirements_hash()
        previous = self.stamp_file.read_text(encoding="utf-8").strip() if self.stamp_file.exists() else ""
        return current != previous

    def requirements_have_entries(self) -> bool:
        if not self.requirements_file.exists():
            return False
        for line in self.requirements_file.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if stripped and not stripped.startswith("#"):
                return True
        return False


def main() -> int:
    env = SkillEnvironment()
    try:
        env.ensure()
    except subprocess.CalledProcessError as exc:
        print(f"Dependency installation failed: {exc}", file=sys.stderr)
        return exc.returncode or 1
    print(f"Environment ready: {env.python}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
