from pathlib import Path
from typing import Any

import structlog
import yaml  # type: ignore[import-untyped]

logger = structlog.get_logger()


def load_yaml_config(config_path: str, defaults: dict[str, Any] | None = None) -> dict[str, Any]:
    path = Path(config_path)

    if not path.exists():
        logger.warning("config_not_found", path=config_path)
        return defaults or {}

    with open(path) as f:
        return yaml.safe_load(f) or {}
