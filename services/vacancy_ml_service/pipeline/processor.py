"""
Обработка одной сырой вакансии: извлечение навыков и уровня.
"""

from uuid import UUID
from typing import Any, Dict, List, Optional

from .skills import extract_skills
from .grade import predict_grade


def process_raw_vacancy(
    raw_vacancy_uuid: UUID,
    title: str = "",
    description: str = "",
    full_text: Optional[str] = None,
    raw_data: Optional[Dict[str, Any]] = None,
) -> tuple[Dict[str, List[str]], Optional[str]]:
    """
    Обрабатывает сырую вакансию и возвращает (skills, grade_prediction).

    Args:
        raw_vacancy_uuid: UUID сырой вакансии
        title: заголовок
        description: описание
        full_text: полный текст (если передан, используется вместо title+description)
        raw_data: JSON с key_skills и др.

    Returns:
        (skills: Dict[str, List[str]], grade_prediction: str | None)
    """
    raw_data = raw_data or {}
    text_for_grade = full_text or f"{title or ''} {description or ''}"

    skills = extract_skills(raw_data=raw_data)
    grade = predict_grade(title=title, description=text_for_grade)

    return skills, grade
