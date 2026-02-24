from __future__ import annotations

from dataclasses import dataclass

from bulldogent.util import PROJECT_ROOT, load_yaml_config

_OBSERVABILITY_CONFIG_PATH = PROJECT_ROOT / "config" / "observability.yaml"


@dataclass
class EventStageConfig:
    enabled: bool

    @classmethod
    def load(cls) -> EventStageConfig:
        full = load_yaml_config(_OBSERVABILITY_CONFIG_PATH)
        raw = full.get("events", {})
        enabled = raw.get("enabled", False)
        return cls(enabled=enabled)
