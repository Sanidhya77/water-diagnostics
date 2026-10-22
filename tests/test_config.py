"""Offline checks for configuration precedence and secret handling."""

import os

from water_diagnostics.config import DEFAULT_BASE_URL, DEFAULT_MODEL, load_settings


def clear_settings_environment(monkeypatch):
    for name in ("NEBIUS_API_KEY", "NEBIUS_BASE_URL", "NEBIUS_MODEL", "TAVILY_API_KEY"):
        monkeypatch.delenv(name, raising=False)


def test_missing_file_allows_offline_defaults(tmp_path, monkeypatch):
    clear_settings_environment(monkeypatch)
    settings = load_settings(tmp_path / "missing.env")
    assert settings.nebius_base_url == DEFAULT_BASE_URL
    assert settings.nebius_model == DEFAULT_MODEL
    assert settings.nebius_api_key.get_secret_value() == ""
    assert settings.tavily_api_key.get_secret_value() == ""


def test_local_secrets_remain_literal_and_are_not_exposed(tmp_path, monkeypatch):
    clear_settings_environment(monkeypatch)
    env_file = tmp_path / ".env"
    env_file.write_text(
        "NEBIUS_API_KEY=synthetic-${UNCHANGED}-key\nTAVILY_API_KEY=synthetic-tavily\n",
        encoding="utf-8",
    )
    before = dict(os.environ)
    settings = load_settings(env_file)
    assert settings.nebius_api_key.get_secret_value() == "synthetic-${UNCHANGED}-key"
    assert settings.tavily_api_key.get_secret_value() == "synthetic-tavily"
    assert "synthetic" not in repr(settings)
    assert "synthetic" not in settings.model_dump_json()
    assert dict(os.environ) == before


def test_process_environment_overrides_local_file(tmp_path, monkeypatch):
    clear_settings_environment(monkeypatch)
    env_file = tmp_path / ".env"
    env_file.write_text("NEBIUS_API_KEY=synthetic-file\nNEBIUS_MODEL=file-model\n", encoding="utf-8")
    monkeypatch.setenv("NEBIUS_API_KEY", "synthetic-process")
    monkeypatch.setenv("NEBIUS_MODEL", "process-model")
    settings = load_settings(env_file)
    assert settings.nebius_api_key.get_secret_value() == "synthetic-process"
    assert settings.nebius_model == "process-model"
