import pytest

import bulldogent.util.db as db_module


class TestConfigureEngine:
    def test_configure_engine_returns_engine(self) -> None:
        engine = db_module.configure_engine("sqlite:///:memory:")
        assert engine is not None

    def test_configure_engine_sets_module_engine(self) -> None:
        db_module.configure_engine("sqlite:///:memory:")
        engine = db_module.get_engine()
        assert engine is not None

    def teardown_method(self) -> None:
        # Reset module-level engine to avoid polluting other tests
        db_module._engine = None


class TestGetEngine:
    def setup_method(self) -> None:
        db_module._engine = None

    def test_raises_before_configure(self) -> None:
        with pytest.raises(RuntimeError, match="Database engine not configured"):
            db_module.get_engine()

    def test_returns_engine_after_configure(self) -> None:
        db_module.configure_engine("sqlite:///:memory:")
        engine = db_module.get_engine()
        assert engine is not None

    def teardown_method(self) -> None:
        db_module._engine = None


class TestGetSession:
    def setup_method(self) -> None:
        db_module._engine = None

    def test_get_session_yields_session(self) -> None:
        db_module.configure_engine("sqlite:///:memory:")
        with db_module.get_session() as session:
            assert session is not None
            # Session should be usable
            result = session.execute(db_module.text("SELECT 1"))
            assert result.scalar() == 1

    def test_get_session_raises_without_engine(self) -> None:
        with pytest.raises(RuntimeError), db_module.get_session():
            pass

    def teardown_method(self) -> None:
        db_module._engine = None
