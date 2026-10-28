"""Build a small source test build from an explicit allowlist; no network calls."""

import argparse
import hashlib
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile


ROOT = Path(__file__).resolve().parent.parent
REPORTS = (
    "RIVER-udall-20240402T220000Z-offline",
    "RIVER-udall-20240403T000000Z-nebius",
    "SIM-002-000-nebius-retry",
    "SIM-005-000-nebius-retry",
    "SIM-006-000-nebius",
)
FIXED_FILES = (
    "README.md", "JUDGE_GUIDE.md", "THIRD_PARTY.md", "LICENSE", "DESIGN.md",
    "HOSTING.md", "USEFULNESS_AND_PILOT.md", "render.yaml", ".python-version",
    "requirements.txt", "requirements-tested.txt", "run_demo.py", "verify_setup.py",
    "pyproject.toml", ".env.example", ".gitignore", "SUBMISSION_DRAFT.md", "RECORD_TODAY.md",
    ".github/workflows/verify.yml", "demo_reports/README.md",
    "scripts/build_demo.py", "SUBMISSION_CHECKLIST.md", "DEMO_SCRIPT.md", "EVALUATION_PLAN.md",
    "data/river/udall-2024-04-01/observations.json",
    "data/river/udall-2024-04-01/context.json",
    "data/river/udall-2024-04-01/README.md",
    "scripts/evaluate_river_holdout.py",
    "data/river/udall-2024-04-08/observations.json",
    "data/river/udall-2024-04-08/context.json",
    "data/river/udall-2024-04-08/README.md",
    "evaluations/river-holdout-2024-04-08/selection.json",
    "evaluations/river-holdout-2024-04-08/README.md",
)
WEB_FILES = ("index.html", "style.css", "app.js", "plex-regular.ttf",
             "plex-semibold.ttf", "OFL-Plex.txt")


def release_files(root=ROOT):
    """No recursive copy of the workspace, generated reports or archives."""
    files = {root / name for name in FIXED_FILES}
    files.update(root / "water_diagnostics" / "web" / name for name in WEB_FILES)
    files.update(root / "reports" / (name + suffix) for name in REPORTS
                 for suffix in (".json", ".md"))
    demo_stems = tuple(f"SIM-{i:03d}-000-nebius" for i in range(1, 7)) + (
        "RIVER-udall-20240402T220000Z-nebius", "RIVER-udall-20240403T000000Z-nebius",
        "RIVER-udall-20240412T000000Z-nebius")
    files.update(root / "demo_reports" / (stem + suffix) for stem in demo_stems for suffix in (".json", ".md"))
    qualification = root / "qualification/2026-10-28"
    files.update(qualification / name for name in (
        "README.md", "fresh-results.json", "browser-api-check.json", "fresh-install.json", "operator-case.json",
        "history/phase-1.json", "history/phase-2.json", "history/phase-3.json",
        "history/incomplete-RIVER-udall-20240402T220000Z-nebius.json",
        "history/incomplete-RIVER-udall-20240402T220000Z-nebius.md",
        "history/before-operator-actions-RIVER-udall-20240412T000000Z-nebius.json",
        "history/before-operator-actions-RIVER-udall-20240412T000000Z-nebius.md"))
    for run in ("local-checks", "reviewed-checks"):
        folder = root / "evaluations/river-holdout-2024-04-08" / run
        files.update(folder / (stem + suffix)
            for stem in ("comparison", "RIVER-udall-20240410T000000Z-offline",
                         "RIVER-udall-20240412T000000Z-offline", "RIVER-udall-20240415T000000Z-offline")
            for suffix in (".json", ".md"))
    for folder in ("water_diagnostics", "tests"):
        files.update((root / folder).rglob("*.py"))
    for path in files:
        if path.is_symlink() or not path.is_file() or not path.resolve().is_relative_to(root.resolve()):
            raise ValueError("A required release file is missing or is not a regular project file.")
    return sorted(files, key=lambda path: path.relative_to(root).as_posix())


def local_secrets(root):
    # Compare exact local values without printing or copying them into artifacts.
    values = [os.environ.get(name, "") for name in ("NEBIUS_API_KEY", "TAVILY_API_KEY")]
    env_file = root / ".env"
    if env_file.is_file():
        for line in env_file.read_text(encoding="utf-8-sig").splitlines():
            key, separator, value = line.partition("=")
            if separator and key.strip() in ("NEBIUS_API_KEY", "TAVILY_API_KEY"):
                values.append(value.strip().strip("\"'"))
    return [value.encode() for value in values if len(value) >= 12]


def build(output, root=ROOT):
    files = release_files(root)
    secrets = local_secrets(root)
    payloads = []
    for path in files:
        relative = path.relative_to(root).as_posix()
        content = path.read_bytes()
        if any(secret in content for secret in secrets):
            raise ValueError("A release file contains a local credential. Build stopped.")
        if path.suffix != ".ttf" and re.search(rb"[A-Za-z]:\\(?:\\)?Users\\", content):
            raise ValueError("A release file contains a personal Windows path. Build stopped.")
        payloads.append((relative, content))
    manifest = {"format": 1, "created_utc": datetime.now(timezone.utc).isoformat(),
                "contains_credentials": False, "contains_model_weights": False,
                "contains_retrospective_qc": False,
                "reports": "Saved prior inference; no new API requests during build.",
                "files": [{"path": name, "bytes": len(data),
                           "sha256": hashlib.sha256(data).hexdigest()}
                          for name, data in payloads]}
    output.parent.mkdir(parents=True, exist_ok=True)
    # Exclusive creation preserves earlier builds.
    with ZipFile(output, "x", compression=ZIP_DEFLATED) as archive:
        for name, content in payloads:
            archive.writestr("water-diagnostics/" + name, content)
        archive.writestr("water-diagnostics/BUILD_MANIFEST.json",
                         json.dumps(manifest, indent=2) + "\n")
    return {"archive": str(output.resolve()), "files": len(payloads),
            "bytes": output.stat().st_size,
            "sha256": hashlib.sha256(output.read_bytes()).hexdigest()}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "dist" /
                        ("water-diagnostics-demo-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + ".zip"))
    args = parser.parse_args()
    print(json.dumps(build(args.output), indent=2))
