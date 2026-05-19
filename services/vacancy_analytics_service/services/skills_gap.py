"""Нормализация навыков и расчёт пересечения / skill gap (кандидат vs вакансия)."""
from __future__ import annotations

import json
from typing import Any


def normalize_skill(s: str) -> str:
    return str(s).strip().lower()


def normalize_skill_set(skills: list[str]) -> set[str]:
    return {normalize_skill(s) for s in skills if s and str(s).strip()}


def vacancy_key_skills_from_json(skills_val: Any) -> list[str]:
    """Извлекает key_skills из JSONB processed_vacancies.skills (как в pipeline)."""
    data: dict = {}
    if skills_val is None:
        return []
    if isinstance(skills_val, dict):
        data = skills_val
    elif isinstance(skills_val, str):
        try:
            data = json.loads(skills_val)
        except json.JSONDecodeError:
            return []
    else:
        return []
    ks = data.get("key_skills", [])
    if not isinstance(ks, list):
        return []
    return [str(x) for x in ks if x is not None and str(x).strip()]


def jaccard_skills(candidate: set[str], vacancy: set[str]) -> float:
    """Коэффициент Жаккара по множествам навыков [0, 1]."""
    if not candidate and not vacancy:
        return 1.0
    if not candidate or not vacancy:
        return 0.0
    inter = len(candidate & vacancy)
    union = len(candidate | vacancy)
    return inter / union if union else 0.0


def match_and_missing(
    candidate_skills: list[str],
    vacancy_skills: list[str],
) -> tuple[list[str], list[str]]:
    """
    Совпавшие и недостающие у кандидата относительно требований вакансии.
    missing = навыки вакансии, которых нет у кандидата.
    """
    c = normalize_skill_set(candidate_skills)
    v = normalize_skill_set(vacancy_skills)
    matched = sorted(c & v, key=lambda x: x)
    missing = sorted(v - c, key=lambda x: x)
    return matched, missing
