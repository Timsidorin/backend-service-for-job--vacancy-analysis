import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, AsyncGenerator, Dict, List, Optional

import httpx

from libs.common.schemas.vacancy import RawVacancyCreate
from services.vacancy_collector_service.connectors.base import BaseConnector

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


class HHConnector(BaseConnector):
    """HH API connector for realtime vacancy collection."""

    BASE_URL = "https://api.hh.ru/vacancies"
    HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
    }

    def __init__(self, per_page: int = 100, max_pages_per_term: int = 20) -> None:
        self.per_page = per_page
        self.max_pages_per_term = max_pages_per_term
        self.search_terms: List[str] = [
            "Менеджер",
            "Продавец",
            "Водитель",
            "Инженер",
            "Врач",
            "Программист",
            "Бухгалтер",
            "Учитель",
            "Повар",
            "Курьер",
            "Дизайнер",
            "Юрист",
            "Администратор",
            "Строитель",
            "Аналитик",
            "HR",
            "Официант",
            "Охранник",
            "Маркетолог",
            "Экономист",
        ]

    async def _get_vacancies_page(
        self,
        client: httpx.AsyncClient,
        *,
        page: int,
        text: str,
    ) -> List[Dict[str, Any]]:
        params = {"page": page, "per_page": self.per_page, "text": text}
        resp = await client.get(self.BASE_URL, headers=self.HEADERS, params=params, timeout=15.0)
        resp.raise_for_status()
        data = resp.json()
        return data.get("items", []) or []

    @staticmethod
    def _parse_published_at(raw: Optional[str]) -> Optional[datetime]:
        if not raw:
            return None
        try:
            normalized = raw.replace("Z", "+00:00")
            dt = datetime.fromisoformat(normalized)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except Exception:
            return None

    @staticmethod
    def _item_to_dto(item: Dict[str, Any]) -> RawVacancyCreate:
        salary = item.get("salary") or {}
        snippet = item.get("snippet") or {}
        employer = item.get("employer") or {}
        area = item.get("area") or {}

        published_at = HHConnector._parse_published_at(item.get("published_at"))

        description_parts: List[str] = []
        if snippet.get("responsibility"):
            description_parts.append(snippet["responsibility"])
        if snippet.get("requirement"):
            description_parts.append(snippet["requirement"])

        return RawVacancyCreate(
            source="hh.ru",
            url=item.get("alternate_url") or "",
            title=item.get("name") or "",
            description="\n".join(description_parts) or None,
            full_text=None,
            city=area.get("name"),
            region=None,
            region_code=None,
            employer=employer.get("name"),
            salary_from=salary.get("from"),
            salary_to=salary.get("to"),
            currency=salary.get("currency"),
            published_at=published_at,
            raw_data=item,
        )

    async def collect_vacancies(
        self,
        since: Optional[datetime] = None,
    ) -> AsyncGenerator[RawVacancyCreate, None]:
        """Yield only vacancies newer than `since`."""
        if since and since.tzinfo is None:
            since = since.replace(tzinfo=timezone.utc)

        async with httpx.AsyncClient() as client:
            for term in self.search_terms:
                logger.info("HHConnector: fetch term '%s'", term)
                stop_term = False
                for page in range(self.max_pages_per_term):
                    try:
                        items = await self._get_vacancies_page(client, page=page, text=term)
                    except Exception as exc:  # noqa: BLE001
                        logger.error("HHConnector: error on term '%s', page %d: %s", term, page, exc)
                        break

                    if not items:
                        break

                    for item in items:
                        published_at = self._parse_published_at(item.get("published_at"))
                        if since and published_at and published_at <= since:
                            stop_term = True
                            continue

                        dto = self._item_to_dto(item)
                        yield dto

                    if stop_term:
                        break
                    await asyncio.sleep(0.2)

