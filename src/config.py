# ============================================================
# src/config.py — Configuration loader
# Western Ghats Endangered Animal Detection project.
# Reads config/settings.yaml and exposes a typed config object.
# ============================================================

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml


# Root of the project (two levels up from this file: src/ -> project root)
PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = PROJECT_ROOT / "config" / "settings.yaml"


def load_config(config_path: Path | str = CONFIG_PATH) -> dict[str, Any]:
    """Load the YAML config file and resolve relative paths to absolute paths.

    Args:
        config_path: Path to the YAML configuration file.

    Returns:
        Dictionary with the full configuration.

    Raises:
        FileNotFoundError: If the config file does not exist.
        yaml.YAMLError: If the file cannot be parsed.
    """
    config_path = Path(config_path)
    if not config_path.exists():
        raise FileNotFoundError(
            f"Configuration file not found: {config_path}\n"
            "Expected location: config/settings.yaml"
        )

    with open(config_path, "r", encoding="utf-8") as f:
        cfg: dict[str, Any] = yaml.safe_load(f)

    if cfg is None:
        raise ValueError(f"Configuration file is empty: {config_path}")

    # Resolve all path values relative to the project root
    paths_section = cfg.get("paths", {})
    for key, value in paths_section.items():
        if isinstance(value, str):
            resolved = PROJECT_ROOT / value
            paths_section[key] = str(resolved)

    # Store the project root in the config for convenience
    cfg["project_root"] = str(PROJECT_ROOT)

    return cfg


def get_class_names(cfg: dict[str, Any]) -> list[str]:
    """Return the list of class names defined in the config."""
    return cfg.get("classes", ["animal"])


def get_species_info(cfg: dict[str, Any]) -> dict[str, dict[str, str]]:
    """Return the species_info dict from settings.yaml.

    Each key is a class name; value is a dict with keys:
      scientific_name, iucn_status, iucn_code, region, description.

    Returns an empty dict if species_info is not configured.
    """
    return cfg.get("species_info", {})


def get_project_metadata(cfg: dict[str, Any]) -> dict[str, str]:
    """Return top-level project metadata (name, region, version, description)."""
    return cfg.get("project", {})


def get_model_checkpoint(cfg: dict[str, Any]) -> str:
    """Return the path to the best available model checkpoint.

    Preference order:
      1. trained_checkpoint (user's own trained model)
      2. pretrained_checkpoint (generic Ultralytics checkpoint)
    """
    trained = cfg.get("model", {}).get("trained_checkpoint")
    if trained:
        # Resolve relative paths against the project root so the check works
        # regardless of the working directory Streamlit was launched from.
        trained_path = Path(trained)
        if not trained_path.is_absolute():
            trained_path = PROJECT_ROOT / trained_path
        if trained_path.is_file():
            return str(trained_path)

    pretrained = cfg.get("model", {}).get("pretrained_checkpoint", "yolov8n.pt")
    # If it is just a filename (no directory), Ultralytics handles the download.
    return pretrained


def is_trained_model_available(cfg: dict[str, Any]) -> bool:
    """Return True if a user-trained model checkpoint exists on disk."""
    trained = cfg.get("model", {}).get("trained_checkpoint")
    if not trained:
        return False
    trained_path = Path(trained)
    if not trained_path.is_absolute():
        trained_path = PROJECT_ROOT / trained_path
    return trained_path.is_file()


if __name__ == "__main__":
    cfg = load_config()
    meta = get_project_metadata(cfg)
    print("Configuration loaded successfully.")
    print(f"  Project      : {meta.get('name', 'Animal Detection')}")
    print(f"  Region       : {meta.get('region', 'N/A')}")
    print(f"  Project root : {cfg['project_root']}")
    print(f"  Classes ({len(get_class_names(cfg))}) : {get_class_names(cfg)}")
    print(f"  Checkpoint   : {get_model_checkpoint(cfg)}")
    print(f"  Trained model: {is_trained_model_available(cfg)}")
