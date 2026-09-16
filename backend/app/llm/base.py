from abc import ABC, abstractmethod
from collections.abc import AsyncIterator


class LLMProvider(ABC):
    @abstractmethod
    async def generate(self, prompt: str, *, system: str | None = None) -> str:
        raise NotImplementedError

    @abstractmethod
    def stream(self, prompt: str, *, system: str | None = None) -> AsyncIterator[str]:
        raise NotImplementedError

    @abstractmethod
    def check(self) -> bool:
        raise NotImplementedError