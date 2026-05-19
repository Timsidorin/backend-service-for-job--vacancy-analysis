"""
Определение профессиональных интересов пользователя по подпискам VK.

Два этапа:
 1. Получение названий сообществ через VK API groups.get
 2. Определение профессий через LLM
"""
import json
import logging

import httpx

logger = logging.getLogger(__name__)

VK_API_GROUPS = "https://api.vk.com/method/groups.get"


def get_vk_group_names(vk_token: str, vk_user_id: int) -> list[str]:
    """Возвращает список названий сообществ пользователя VK."""
    names: list[str] = []
    offset = 0
    with httpx.Client(timeout=30.0) as client:
        while True:
            r = client.get(
                VK_API_GROUPS,
                params={
                    "access_token": vk_token,
                    "v": "5.131",
                    "extended": 1,
                    "count": 1000,
                    "offset": offset,
                    "user_id": vk_user_id,
                },
            )
            data = r.json()
            if "error" in data:
                raise ValueError(data["error"].get("error_msg", str(data["error"])))
            items = data.get("response", {}).get("items", [])
            if not items:
                break
            names.extend(g.get("name", "") for g in items)
            if len(items) < 1000:
                break
            offset += 1000
    return names


def infer_professions(
    group_names: list[str],
    *,
    api_key: str,
    base_url: str | None = None,
    model: str = "qwen/qwen3-vl-flash",
) -> list[str]:
    """По названиям сообществ возвращает 3-5 профессий через LLM."""
    import openai

    client = openai.OpenAI(api_key=api_key, base_url=base_url or None)
    prompt = (
        "Проанализируй список сообществ ВКонтакте и предложи 3-5 реальных профессий, "
        "наиболее соответствующих интересам пользователя. Используй стандартные названия профессий "
        "на русском языке. "
        'Верни ТОЛЬКО JSON-объект вида: {"professions": ["профессия1", "профессия2"]}.\n'
        "Input: " + repr(group_names[:200]) + "\n"
        'Output ONLY JSON: {"professions": ["prof1", "prof2"]} (3-5 items, specific).'
    )
    resp = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
    )
    text = (resp.choices[0].message.content or "").strip()

    if "{" in text:
        text = text[text.find("{"):]
    if "}" in text:
        text = text[: text.rfind("}") + 1]

    obj = json.loads(text)
    return obj.get("professions", [])[:10]


def get_professions_by_vk_user(
    vk_token: str,
    vk_user_id: int,
    *,
    api_key: str,
    base_url: str | None = None,
    model: str = "qwen/qwen3-vl-flash",
) -> list[str]:
    """Полный пайплайн: VK groups → LLM → профессии."""
    group_names = get_vk_group_names(vk_token, vk_user_id)
    if not group_names:
        return []
    return infer_professions(
        group_names, api_key=api_key, base_url=base_url, model=model,
    )
