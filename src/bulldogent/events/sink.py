from abc import ABC, abstractmethod


class AbstractEventSink(ABC):
    @abstractmethod
    def push(self, batch_size: int = 500) -> int:
        """Push staged events to the external sink. Returns count of pushed rows."""
        ...

    @abstractmethod
    def close(self) -> None: ...
