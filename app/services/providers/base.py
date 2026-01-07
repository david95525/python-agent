from abc import ABC, abstractmethod


class BaseAIProvider(ABC):
    @abstractmethod
    async def generate_response(self, message: str, context: str, history: list) -> str:
        pass
