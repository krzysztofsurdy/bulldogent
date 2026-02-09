from pathlib import Path
from typing import Any

import structlog
import yaml  # type: ignore[import-untyped]

logger = structlog.get_logger()


def load_yaml_config(config_path: Path, defaults: dict[str, Any] | None = None) -> dict[str, Any]:
    if not config_path.exists():
        logger.warning("config_not_found", path=config_path)
        return defaults or {}

    with open(config_path) as f:
        return yaml.safe_load(f) or {}
