"""
Сервис эмбеддингов для семантического поиска вакансий.
Использует OpenAI text-embedding-3-small (1536 dim).
"""
import logging

logger = logging.getLogger(__name__)

EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIM = 1536


def build_vacancy_text(title: str, description: str | None, domain: str | None, key_skills: list[str]) -> str:
    """Собирает текст вакансии для эмбеддинга."""
    parts = [title or "", description or "", domain or ""]
    if key_skills:
        parts.append(" ".join(str(s) for s in key_skills[:50]))
    return " ".join(p.strip() for p in parts if p.strip())[:8000]


def build_user_profile_text(professions: list[str]) -> str:
    """Собирает текст профиля пользователя (профессии) для эмбеддинга."""
    return " ".join(str(p).strip() for p in professions if p)[:2000]


def build_candidate_profile_text(profile_json: dict) -> str:
    """Собирает текст профиля соискателя из структурированного JSON (после LLM) для эмбеддинга."""
    skills = profile_json.get("skills") or []
    titles = profile_json.get("desired_titles") or []
    summary = (profile_json.get("summary") or "").strip()
    parts: list[str] = []
    if summary:
        parts.append(summary)
    if titles:
        parts.append(" ".join(str(t).strip() for t in titles if t))
    if skills:
        parts.append(" ".join(str(s).strip() for s in skills[:100] if s))
    return " ".join(p for p in parts if p)[:8000]


def get_embedding(
    text: str,
    *,
    api_key: str,
    base_url: str | None = None,
    model: str = EMBEDDING_MODEL,
) -> list[float]:
    """Возвращает вектор эмбеддинга для текста."""
    import openai
    client = openai.OpenAI(api_key=api_key, base_url=base_url or None)
    r = client.embeddings.create(input=[text[:8000]], model=model)
    return r.data[0].embedding


def get_embeddings_batch(
    texts: list[str],
    *,
    api_key: str,
    base_url: str | None = None,
    model: str = EMBEDDING_MODEL,
    batch_size: int = 100,
) -> list[list[float]]:
    """Возвращает эмбеддинги для батча текстов (синхронно)."""
    import openai
    client = openai.OpenAI(api_key=api_key, base_url=base_url or None)
    out: list[list[float]] = []
    for i in range(0, len(texts), batch_size):
        batch = [t[:8000] for t in texts[i : i + batch_size]]
        r = client.embeddings.create(input=batch, model=model)
        out.extend(d.embedding for d in r.data)
    return out


async def get_embeddings_batch_async(
    texts: list[str],
    *,
    api_key: str,
    base_url: str | None = None,
    model: str = EMBEDDING_MODEL,
) -> list[list[float]]:
    """Асинхронно получает эмбеддинги (один запрос на весь батч)."""
    from openai import AsyncOpenAI
    client = AsyncOpenAI(api_key=api_key, base_url=base_url or None)
    batch = [t[:8000] for t in texts]
    r = await client.embeddings.create(input=batch, model=model)
    return [d.embedding for d in r.data]
