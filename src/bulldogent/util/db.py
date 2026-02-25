from collections.abc import Generator
from contextlib import contextmanager

import structlog
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.orm import Session

_logger = structlog.get_logger()

_engine: Engine | None = None


def configure_engine(database_url: str) -> Engine:
    global _engine  # noqa: PLW0603
    _engine = create_engine(database_url, pool_pre_ping=True)
    _logger.info("db_engine_configured", url=database_url.split("@")[-1])
    return _engine


def get_engine() -> Engine:
    if _engine is None:
        raise RuntimeError("Database engine not configured — call configure_engine() first")
    return _engine


@contextmanager
def get_session() -> Generator[Session, None, None]:
    with Session(get_engine()) as session:
        yield session


def init_db() -> None:
    engine = get_engine()
    with engine.connect() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        conn.commit()

    from bulldogent.baseline.models import Base

    Base.metadata.create_all(engine)
    _logger.info("db_initialized")
