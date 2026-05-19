import logging
import random
from datetime import datetime
from typing import Any, AsyncGenerator, Dict, List, Optional

import asyncio
import httpx
from bs4 import BeautifulSoup

from libs.common.schemas.vacancy import RawVacancyCreate
from services.vacancy_collector_service.connectors.base import BaseConnector

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


class AvitoConnector(BaseConnector):
    """Avito connector that parses the first results page."""

    BASE_URL = "https://www.avito.ru/all/vakansii"

    USER_AGENTS = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    ]

    def __init__(self, search_term: str = "Работа") -> None:
        self.search_term = search_term

    async def _get_html(self, client: httpx.AsyncClient, url: str) -> Optional[str]:
        headers = {
            "User-Agent": random.choice(self.USER_AGENTS),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
            "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
            "Cache-Control": "max-age=0",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
            "Referer": "https://www.google.com/",
        }

        retries = 3
        backoff = 5

        for attempt in range(retries):
            try:
                resp = await client.get(url, headers=headers, timeout=15.0)
                if resp.status_code == 429:
                    logger.warning("Avito: 429 Too Many Requests. Waiting %d seconds...", backoff)
                    await asyncio.sleep(backoff)
                    backoff *= 2
                    continue
                resp.raise_for_status()
                return resp.text
            except Exception as exc:  # noqa: BLE001
                logger.error("Avito: error fetching %s: %s", url, exc)
                if attempt < retries - 1:
                    await asyncio.sleep(2)
                else:
                    return None
        return None

    @staticmethod
    def _item_to_dto(item) -> RawVacancyCreate:
        title_tag = item.find("a", {"data-marker": "item-title"})
        name = title_tag.get("title") if title_tag else "Unknown"
        href = title_tag.get("href") if title_tag else ""
        full_url = f"https://www.avito.ru{href}" if href else ""

        item_id = item.get("data-item-id") or "0"

        price_tag = item.find("meta", {"itemprop": "price"})
        salary_from = None
        if price_tag and price_tag.get("content"):
            try:
                salary_from = int(price_tag.get("content"))
            except ValueError:
                salary_from = None

        desc_tag = item.find("div", {"class": "iva-item-description"})
        snippet = desc_tag.get_text(strip=True) if desc_tag else ""

        geo_tag = item.find("div", {"data-marker": "item-line"})
        area = geo_tag.get_text(strip=True) if geo_tag else "Unknown"

        # Avito does not provide exact publication time in this feed.
        published_at = datetime.utcnow()

        return RawVacancyCreate(
            source="avito",
            url=full_url,
            title=name,
            description=snippet or None,
            full_text=None,
            city=area,
            region=None,
            region_code=None,
            employer=None,
            salary_from=salary_from,
            salary_to=None,
            currency="RUB",
            published_at=published_at,
            raw_data={"id": item_id},
        )

    async def collect_vacancies(
        self,
        since: Optional[datetime] = None,
    ) -> AsyncGenerator[RawVacancyCreate, None]:
        """Возвращает верхушку выдачи Avito. Фильтрация по since приблизительная."""
        url = f"{self.BASE_URL}?q={self.search_term}"
        async with httpx.AsyncClient() as client:
            logger.info("AvitoConnector: fetching %s", url)
            html = await self._get_html(client, url)
            if not html:
                return

        def _parse(html_text: str) -> List[Any]:
            soup = BeautifulSoup(html_text, "html.parser")
            return soup.find_all("div", {"data-marker": "item"})

        loop = asyncio.get_event_loop()
        items = await loop.run_in_executor(None, _parse, html)

        if not items:
            logger.warning("AvitoConnector: no items found on page")
            return

        for item in items:
            dto = self._item_to_dto(item)
            if since and dto.published_at and dto.published_at <= since:
                continue
            yield dto
