from pathlib import Path

from bulldogent.util.yaml import load_yaml_config

PROJECT_ROOT = Path(__file__).resolve().parents[3]

__all__ = ["PROJECT_ROOT", "load_yaml_config"]
