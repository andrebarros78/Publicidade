from abc import ABC, abstractmethod
from typing import Any
from app.core.models import ActionRequest

class AdsAdapter(ABC):
    @abstractmethod
    async def health(self) -> dict[str, Any]: ...
    @abstractmethod
    async def list_campaigns(self) -> dict[str, Any]: ...
    @abstractmethod
    async def execute(self, req: ActionRequest) -> dict[str, Any]: ...
