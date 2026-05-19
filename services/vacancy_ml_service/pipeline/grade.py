"""
Предсказание уровня (Junior/Middle/Senior) по правилам на основе title и description.
"""

import re
from typing import Optional

# Ключевые фразы для каждого уровня (lowercase)
JUNIOR_PHRASES = [
    "junior", "джуниор", "начинающий", "intern", "стажер", "без опыта",
    "от 0 лет", "0+ лет", "опыт не обязателен", "без требований к опыту",
    "для начинающих", "обучение", "молодой специалист", "входной уровень",
]

MIDDLE_PHRASES = [
    "middle", "мидл", "миддл", "от 1 года", "1+ лет", "от 2 лет", "2+ лет",
    "от 3 лет", "3+ лет", "опыт от 1 года", "опыт от 2 лет", "опыт от 3 лет",
    "опыт 1-3", "опыт 2-5", "средний уровень", "middle/senior",
]

SENIOR_PHRASES = [
    "senior", "сеньор", "lead", "лид", "principal", "architect", "архитектор",
    "тимлид", "team lead", "от 5 лет", "5+ лет", "от 6 лет", "опыт от 5",
    "опыт 5+", "senior/lead", "ведущий", "главный", "руководитель",
]


def predict_grade(title: str = "", description: str = "") -> Optional[str]:
    """
    Определяет уровень по ключевым фразам в заголовке и описании.
    Приоритет: Senior > Middle > Junior (более высокий уровень "перебивает").
    """
    if not title and not description:
        return None

    text = f" {title or ''} {description or ''} ".lower()

    is_junior = any(p in text for p in JUNIOR_PHRASES)
    is_middle = any(p in text for p in MIDDLE_PHRASES)
    is_senior = any(p in text for p in SENIOR_PHRASES)

    # Явные числа лет
    years_match = re.search(r"(?:опыт|от)\s*(\d+)\s*\+?\s*лет?", text)
    if years_match:
        years = int(years_match.group(1))
        if years >= 5:
            is_senior = True
        elif years >= 2:
            is_middle = True
        elif years == 0:
            is_junior = True

    if is_senior:
        return "Senior"
    if is_middle:
        return "Middle"
    if is_junior:
        return "Junior"

    return None
