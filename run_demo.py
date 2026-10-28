"""Set up an isolated environment and run the source demo on Windows/macOS/Linux."""

import argparse
import hashlib
import os
from pathlib import Path
import subprocess
import sys
import venv


ROOT = Path(__file__).resolve().parent


def main():
    if sys.version_info < (3, 11):
        raise SystemExit("Install Python 3.11 or newer, then run this file again.")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--check", action="store_true", help="Check the installation and saved demo without API requests")
    args = parser.parse_args()
    if not 1024 <= args.port <= 65535:
        parser.error("Choose a port between 1024 and 65535.")
    environment = ROOT / ".venv"
    python = environment / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    requirements = ROOT / "requirements-tested.txt"
    fingerprint = hashlib.sha256(requirements.read_bytes()).hexdigest()
    marker = environment / ".water-diagnostics-requirements"
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    if not python.is_file():
        print("Creating the local Python environment…", flush=True)
        venv.create(environment, with_pip=True)
    if not marker.is_file() or marker.read_text(encoding="utf-8") != fingerprint:
        print("Installing the tested dependencies. This needs internet access once.", flush=True)
        subprocess.run([str(python), "-m", "pip", "install", "--disable-pip-version-check",
                        "-r", str(requirements)], cwd=ROOT, env=env, check=True)
        marker.write_text(fingerprint, encoding="utf-8")
    if args.check:
        subprocess.run([str(python), "verify_setup.py"], cwd=ROOT, env=env, check=True)
        subprocess.run([str(python), "-m", "water_diagnostics", "validate-demo", "--mode", "saved"],
                       cwd=ROOT, env=env, check=True)
        print("Saved demo verified. No new model request was made.", flush=True)
        return 0
    print("Starting the local workbench. Saved reports and local checks are free.", flush=True)
    try:
        return subprocess.call([str(python), "-m", "water_diagnostics", "serve", "--port", str(args.port)],
                               cwd=ROOT, env=env)
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except subprocess.CalledProcessError as error:
        raise SystemExit("Setup or verification did not complete (exit " + str(error.returncode)
                         + "). Check the message above, then run the launcher again.") from None
