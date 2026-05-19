from abc import ABC, abstractmethod
from datetime import datetime
from typing import AsyncGenerator, Optional

from libs.common.schemas.vacancy import RawVacancyCreate


class BaseConnector(ABC):
    @abstractmethod
    async def collect_vacancies(
        self,
        since: Optional[datetime] = None,
    ) -> AsyncGenerator[RawVacancyCreate, None]:
        """Yield new vacancies, optionally filtered by publication time."""
        ...
