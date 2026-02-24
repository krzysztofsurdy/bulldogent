from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

from bulldogent.util import PROJECT_ROOT, load_yaml_config

_OBSERVABILITY_CONFIG_PATH = PROJECT_ROOT / "config" / "observability.yaml"


class AbstractSinkConfig(ABC):
    @classmethod
    @abstractmethod
    def from_dict(cls, raw: dict[str, Any]) -> AbstractSinkConfig: ...


@dataclass
class SnowflakeSinkConfig(AbstractSinkConfig):
    account: str
    user: str
    password: str
    warehouse: str
    database: str
    schema_name: str
    role: str
    table: str

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> SnowflakeSinkConfig:
        return cls(
            account=raw["account"],
            user=raw["user"],
            password=raw["password"],
            warehouse=raw["warehouse"],
            database=raw["database"],
            schema_name=raw["schema"],
            role=raw["role"],
            table=raw.get("table", "events"),
        )


@dataclass
class EventSinkConfig:
    enabled: bool
    sink_type: str
    sink: AbstractSinkConfig | None

    @classmethod
    def load(cls) -> EventSinkConfig:
        full = load_yaml_config(_OBSERVABILITY_CONFIG_PATH)
        raw = full.get("event_sink", {})
        enabled = raw.get("enabled", False)
        sink_type = raw.get("sink", "")

        if not enabled or not sink_type:
            return cls(enabled=False, sink_type=sink_type, sink=None)

        sink_config: AbstractSinkConfig | None = None
        if sink_type == "snowflake":
            snowflake_raw = raw.get("snowflake", {})
            if snowflake_raw:
                sink_config = SnowflakeSinkConfig.from_dict(snowflake_raw)

        return cls(enabled=enabled, sink_type=sink_type, sink=sink_config)
