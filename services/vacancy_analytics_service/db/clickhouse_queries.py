"""Хелперы для построения запросов к ClickHouse (фильтры)."""
from datetime import date
from typing import Optional


def build_where(
    domain: Optional[str] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    source: Optional[str] = None,
    grade: Optional[str] = None,
) -> tuple[str, dict]:
    """Собирает фрагмент WHERE и словарь params для vacancies_analytics."""
    parts, params = ["1=1"], {}
    if domain:
        parts.append("domain = {domain:String}")
        params["domain"] = domain
    if date_from:
        parts.append("published_date >= {date_from:Date}")
        params["date_from"] = str(date_from)
    if date_to:
        parts.append("published_date <= {date_to:Date}")
        params["date_to"] = str(date_to)
    if source:
        parts.append("source = {source:String}")
        params["source"] = source
    if grade:
        parts.append("grade = {grade:String}")
        params["grade"] = grade
    return " AND ".join(parts), params
