from __future__ import annotations

from pathlib import Path

import yaml

from apix.common.exceptions import ConfigError
from apix.common.logging import backend_root


def load_yaml(name: str) -> dict:
    path = backend_root() / "config" / name
    if not path.exists():
        raise ConfigError(f"Missing config file: {path}")
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ConfigError(f"Config {name} must be a mapping")
    return data


def methodology() -> dict:
    return load_yaml("methodology.yaml")


def routes_config() -> dict:
    return load_yaml("routes.yaml")


def sources_config() -> dict:
    return load_yaml("sources.yaml")


def settings() -> dict:
    return load_yaml("settings.yaml")


def data_dir() -> Path:
    path = backend_root() / "data"
    path.mkdir(parents=True, exist_ok=True)
    return path
