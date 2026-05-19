"""
Извлечение навыков из raw_data.key_skills.
Простой перенос без хардкода: парсим key_skills (строка или список) → список строк.
"""

import json
import re
from typing import Any, Dict, List


def _ensure_dict(raw_data: Any) -> Dict[str, Any]:
    """raw_data из JSONB может быть строкой (двойное кодирование)."""
    if raw_data is None:
        return {}
    if isinstance(raw_data, dict):
        return raw_data
    if isinstance(raw_data, str):
        try:
            return json.loads(raw_data)
        except json.JSONDecodeError:
            return {}
    return {}


def _parse_key_skills(value: Any) -> List[str]:
    """
    Парсит key_skills из raw_data.
    Поддерживает: строка "A,B,C" или "A;B;C", список ["A","B"].
    Сохраняет оригинальное написание (без .lower()/.title()).
    """
    if value is None:
        return []
    if isinstance(value, list):
        return [str(s).strip() for s in value if s is not None and str(s).strip()]
    if isinstance(value, str):
        parts = re.split(r"[,;]\s*|\n", value)
        return [p.strip() for p in parts if p.strip()]
    return []


def extract_skills(raw_data: Any) -> Dict[str, List[str]]:
    """
    Извлекает key_skills из raw_data и возвращает в формате для JSONB.
    raw_data может быть dict или str (JSON-строка при двойном кодировании).

    Returns:
        {"key_skills": ["AutoCAD", "MS Excel", "MS Word", ...]}
        Пустой список если key_skills нет или пустой.
    """
    data = _ensure_dict(raw_data)
    skills = _parse_key_skills(data.get("key_skills"))
    return {"key_skills": skills}
