import os
from pathlib import Path

from bulldogent.util.yaml import load_yaml_config

PROJECT_ROOT = Path(os.environ.get("BULLDOGENT_ROOT", Path.cwd()))

__all__ = ["PROJECT_ROOT", "load_yaml_config"]
