"""Offline dependency and configuration check. Never submits API requests."""

import importlib
from importlib.metadata import version
import sys

from water_diagnostics.config import load_settings


def main() -> None:
    # Preserve the Latvian characters in the project path in redirected output.
    sys.stdout.reconfigure(encoding="utf-8")
    print(f"Python: {sys.version.split()[0]}")
    print(f"Interpreter: {sys.executable}")
    for module_name, distribution_name in (
        ("httpx", "httpx"),
        ("dotenv", "python-dotenv"),
        ("pydantic", "pydantic"),
        ("pytest", "pytest"),
    ):
        importlib.import_module(module_name)
        print(f"OK: {distribution_name} {version(distribution_name)}")
    load_settings()
    print("OK: configuration loaded (secret values omitted)")
    print("Verification passed; no API calls or physical tests performed.")


if __name__ == "__main__":
    main()
