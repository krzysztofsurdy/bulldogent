import logging

from bulldogent.util.logging import configure_logging


class TestConfigureLogging:
    def setup_method(self) -> None:
        root = logging.getLogger()
        self._original_handlers = list(root.handlers)

    def teardown_method(self) -> None:
        root = logging.getLogger()
        root.handlers = list(self._original_handlers)

    def _added_handlers(self) -> list[logging.Handler]:
        root = logging.getLogger()
        return [h for h in root.handlers if h not in self._original_handlers]

    def test_json_output_default(self) -> None:
        configure_logging()

        added = self._added_handlers()
        assert len(added) == 1
        assert isinstance(added[0], logging.StreamHandler)

    def test_console_output(self) -> None:
        configure_logging(json_output=False)

        added = self._added_handlers()
        assert len(added) == 1
        assert isinstance(added[0], logging.StreamHandler)

    def test_log_level_respected(self) -> None:
        configure_logging(log_level="WARNING")

        root = logging.getLogger()
        assert root.level == logging.WARNING

    def test_log_level_debug(self) -> None:
        configure_logging(log_level="DEBUG")

        root = logging.getLogger()
        assert root.level == logging.DEBUG
