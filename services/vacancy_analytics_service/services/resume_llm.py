"""Структурирование резюме через LLM (JSON)."""
from __future__ import annotations

import json
import logging
import re

logger = logging.getLogger(__name__)

RESUME_JSON_SCHEMA_HINT = """
Верни один JSON-объект со полями:
- "skills": массив строк — ключевые технологии и навыки (нормализуй: Python, SQL, …);
- "summary": краткое текстовое резюме профиля (1–3 предложения, на русском если резюме на русском);
- "desired_titles": массив желаемых должностей/ролей;
- "years_experience": число или null — общий стаж в годах, если удаётся оценить.
Без markdown, только валидный JSON.
"""


def structure_resume_profile(
    resume_text: str,
    *,
    api_key: str,
    base_url: str | None,
    model: str,
) -> dict:
    """Вызывает chat completion с response_format json_object."""
    import openai

    text = resume_text.strip()[:24000]
    if not text:
        return {"skills": [], "summary": "", "desired_titles": [], "years_experience": None}

    client = openai.OpenAI(api_key=api_key, base_url=base_url or None)
    try:
        r = client.chat.completions.create(
            model=model,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": "Ты помощник для извлечения структуры из резюме. " + RESUME_JSON_SCHEMA_HINT},
                {"role": "user", "content": text},
            ],
            temperature=0.2,
        )
        raw = (r.choices[0].message.content or "").strip()
        data = json.loads(raw)
    except Exception as e:
        logger.exception("structure_resume_profile LLM failed: %s", e)
        return _fallback_from_text(text)

    return _normalize_profile_dict(data)


def _normalize_profile_dict(data: dict) -> dict:
    skills = data.get("skills") or []
    if not isinstance(skills, list):
        skills = []
    skills = [str(s).strip() for s in skills if s and str(s).strip()][:200]

    titles = data.get("desired_titles") or []
    if not isinstance(titles, list):
        titles = []
    titles = [str(t).strip() for t in titles if t and str(t).strip()][:50]

    summary = data.get("summary") or ""
    if not isinstance(summary, str):
        summary = str(summary)
    summary = summary.strip()[:4000]

    ye = data.get("years_experience")
    if ye is not None and not isinstance(ye, (int, float)):
        try:
            ye = float(ye)
        except (TypeError, ValueError):
            ye = None

    return {
        "skills": skills,
        "summary": summary,
        "desired_titles": titles,
        "years_experience": ye,
    }


def _fallback_from_text(text: str) -> dict:
    """Грубый fallback без LLM: пустой профиль + первые символы как summary."""
    snippet = re.sub(r"\s+", " ", text)[:500]
    return {
        "skills": [],
        "summary": snippet,
        "desired_titles": [],
        "years_experience": None,
    }
