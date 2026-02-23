import os
import re
from pathlib import Path
from typing import Any, cast

import structlog
import yaml  # type: ignore[import-untyped]

logger = structlog.get_logger()

_ENV_PATTERN = re.compile(r"\$\(([^)]+)\)")


def _resolve_env_vars(
    value: Any,
    required_vars: set[str] | None = None,
) -> Any:
    """Recursively resolve ``$(VAR)`` placeholders to environment variables.

    When *required_vars* is provided, any variable name in that set that is
    missing from the environment will raise :class:`ValueError` instead of
    silently falling back to an empty string.
    """

    def _replace(match: re.Match[str]) -> str:
        var_name = match.group(1)
        env_value = os.getenv(var_name)
        if env_value is None and required_vars and var_name in required_vars:
            msg = f"Missing required environment variable: {var_name}"
            raise ValueError(msg)
        return env_value if env_value is not None else ""

    if isinstance(value, str):
        return _ENV_PATTERN.sub(_replace, value)
    if isinstance(value, dict):
        return {k: _resolve_env_vars(v, required_vars) for k, v in value.items()}
    if isinstance(value, list):
        return [_resolve_env_vars(item, required_vars) for item in value]
    return value


def load_yaml_config(
    config_path: Path,
    defaults: dict[str, Any] | None = None,
    required_vars: set[str] | None = None,
) -> dict[str, Any]:
    """Load a YAML config file and resolve ``$(VAR)`` env-var placeholders.

    Args:
        config_path: Path to the YAML file.
        defaults: Fallback dict when the file does not exist.
        required_vars: Set of environment variable names that *must* be
            present.  A :class:`ValueError` is raised when any of these
            are missing from the environment.
    """
    if not config_path.exists():
        logger.warning("config_not_found", path=config_path)
        return defaults or {}

    with open(config_path) as f:
        raw = yaml.safe_load(f) or {}

    resolved: dict[str, Any] = cast(dict[str, Any], _resolve_env_vars(raw, required_vars))
    return resolved
