#!/usr/bin/env python3
"""
Импорт вакансий из experiments/vacancies.csv в таблицу raw_vacancies.

Структура CSV (delimiter ;): пустая колонка, data_source, id, link, last_found_at,
is_open, name, description, salary_from, salary_to, salary, experience, employer_id,
employer_name, employer_type, employer_industry_id, employer_industry_name,
requirements, languages, accept_kids, accept_handicapped, benefits, accomodation,
schedule, employment, country_id, country_name, region_id, region_name,
region_district_id, region_district_name, role_id, role_name, raw_skills, source.

Использование:
    uv run python -m scripts.import_vacancies_csv
    uv run python -m scripts.import_vacancies_csv --limit 1000
    uv run python -m scripts.import_vacancies_csv --path experiments/vacancies.csv
"""
import argparse
import ast
import asyncio
import csv
import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except ImportError:
    pass

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

PG_HOST = os.getenv("DB_HOST", "localhost")
PG_PORT = int(os.getenv("DB_PORT", "5432"))
PG_USER = os.getenv("DATABASE_USERNAME", "postgres")
PG_PASS = os.getenv("DATABASE_PASSWORD", "admin")
PG_NAME = os.getenv("DATABASE_NAME", "job_vacancy")

# Индексы колонок CSV (после пустой колонки 0)
IDX = {
    "data_source": 1,
    "id": 2,
    "link": 3,
    "last_found_at": 4,
    "is_open": 5,
    "name": 6,
    "description": 7,
    "salary_from": 8,
    "salary_to": 9,
    "salary": 10,
    "experience": 11,
    "employer_id": 12,
    "employer_name": 13,
    "employer_type": 14,
    "employer_industry_id": 15,
    "employer_industry_name": 16,
    "requirements": 17,
    "languages": 18,
    "accept_kids": 19,
    "accept_handicapped": 20,
    "benefits": 21,
    "accomodation": 22,
    "schedule": 23,
    "employment": 24,
    "country_id": 25,
    "country_name": 26,
    "region_id": 27,
    "region_name": 28,
    "region_district_id": 29,
    "region_district_name": 30,
    "role_id": 31,
    "role_name": 32,
    "raw_skills": 33,
    "source": 34,
}


def _int(v, default=None):
    if v is None or v == "":
        return default
    try:
        return int(float(v))
    except (ValueError, TypeError):
        return default


def _parse_ts(v):
    if not v or not v.strip():
        return None
    v = v.strip()
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%d.%m.%Y %H:%M:%S", "%d.%m.%Y"):
        try:
            return datetime.strptime(v, fmt)
        except ValueError:
            continue
    return None


def _safe_json(v, default=None):
    if default is None:
        default = {}
    if not v or not v.strip():
        return default
    v = v.strip()
    if v in ("[]", "{}", "null"):
        return default if default is not None else {}
    try:
        return json.loads(v)
    except json.JSONDecodeError:
        return default


def _sanitize_unicode(s: str) -> str:
    """Убирает суррогатные символы (surrogate code points), иначе PostgreSQL/asyncpg падает при UTF-8."""
    if not s:
        return s
    return s.encode("utf-8", errors="replace").decode("utf-8")


def _sanitize_dict(obj):
    """Рекурсивно заменяет строки в dict/list на версии без суррогатов."""
    if isinstance(obj, dict):
        return {k: _sanitize_dict(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_sanitize_dict(x) for x in obj]
    if isinstance(obj, str):
        return _sanitize_unicode(obj)
    return obj


def _parse_raw_skills(v: str) -> list:
    """
    Парсит raw_skills из CSV. В датасете часто Python-литерал ['a', 'b'] (одинарные кавычки),
    а не JSON. Пробуем json.loads, затем ast.literal_eval.
    """
    if not v or not v.strip():
        return []
    v = v.strip()
    if v in ("[]", "{}"):
        return []
    try:
        out = json.loads(v)
        return out if isinstance(out, list) else []
    except json.JSONDecodeError:
        pass
    try:
        out = ast.literal_eval(v)
        return out if isinstance(out, list) else []
    except (ValueError, SyntaxError):
        pass
    return []


def row_to_raw(row: list) -> tuple | None:
    """Преобразует строку CSV в кортеж для INSERT в raw_vacancies."""
    if len(row) <= IDX["source"]:
        return None

    def _get(i: int) -> str:
        return (row[i].strip() if i < len(row) and row[i] else "") or ""

    def _get_null(i: int):
        v = _get(i)
        return v if v else None

    # data_source = платформа (hh, rabotaru, rvr, superjob); колонка "source" = JSON типа публикатора
    source = _get(IDX["data_source"]) or "unknown"
    url = _get(IDX["link"])
    if not url:
        return None

    title = _get_null(IDX["name"]) or _get_null(IDX["role_name"]) or "Без названия"
    description = _get_null(IDX["description"])
    full_text = None
    if description:
        req = _get_null(IDX["requirements"])
        if isinstance(req, str):
            full_text = f"{description}\n{req}" if req else description
        else:
            full_text = description

    city = _get_null(IDX["region_district_name"]) or _get_null(IDX["region_name"])
    region = _get_null(IDX["region_name"])
    region_code = _get_null(IDX["region_id"]) if _get(IDX["region_id"]) else None

    employer = _get_null(IDX["employer_name"])
    salary_from = _int(row[IDX["salary_from"]]) if IDX["salary_from"] < len(row) else None
    salary_to = _int(row[IDX["salary_to"]]) if IDX["salary_to"] < len(row) else None
    if salary_from is not None and salary_from == 0:
        salary_from = None
    if salary_to is not None and salary_to == 0:
        salary_to = None

    published_at = _parse_ts(row[IDX["last_found_at"]] if IDX["last_found_at"] < len(row) else "")

    raw_skills_val = row[IDX["raw_skills"]] if IDX["raw_skills"] < len(row) else ""
    raw_skills = _parse_raw_skills(raw_skills_val)
    key_skills = [str(s).strip() for s in raw_skills if s is not None and str(s).strip()]

    source_type_raw = _get_null(IDX["source"])  # JSON: {"type": "company"} и т.д.
    source_type = _safe_json(source_type_raw) if source_type_raw else None

    raw_data = {
        "external_id": _get(IDX["id"]) or None,
        "key_skills": key_skills,
        "experience": _get_null(IDX["experience"]),
        "requirements": _safe_json(row[IDX["requirements"]] if IDX["requirements"] < len(row) else ""),
        "raw_skills": raw_skills,
        "role_name": _get_null(IDX["role_name"]),
        "employer_type": _get_null(IDX["employer_type"]),
        "employer_industry_name": _get_null(IDX["employer_industry_name"]),
        "role_id": _get_null(IDX["role_id"]),
        "employment": _get_null(IDX["employment"]),
        "schedule": _get_null(IDX["schedule"]),
        "source_type": source_type,
    }
    raw_data = _sanitize_dict(raw_data)

    return (
        _sanitize_unicode(source),
        _sanitize_unicode(url),
        _sanitize_unicode(title) if title else None,
        _sanitize_unicode(description) if description else None,
        _sanitize_unicode(full_text) if full_text else None,
        _sanitize_unicode(city) if city else None,
        _sanitize_unicode(region) if region else None,
        _sanitize_unicode(region_code) if region_code else None,
        _sanitize_unicode(employer) if employer else None,
        salary_from,
        salary_to,
        "RUR",
        published_at,
        json.dumps(raw_data, ensure_ascii=False),
    )


async def run(csv_path: Path, limit: int | None, batch_size: int = 1000):
    try:
        import asyncpg
    except ImportError:
        logger.error("Требуется asyncpg: uv add asyncpg")
        sys.exit(1)

    if not csv_path.exists():
        logger.error("Файл не найден: %s", csv_path)
        sys.exit(1)

    conn = await asyncpg.connect(
        f"postgresql://{PG_USER}:{PG_PASS}@{PG_HOST}:{PG_PORT}/{PG_NAME}"
    )

    try:
        inserted = 0
        skipped = 0

        with open(csv_path, "r", encoding="utf-8", newline="") as f:
            reader = csv.reader(f, delimiter=";")
            header = next(reader)
            if len(header) < 10:
                logger.error("Неверный формат CSV: слишком мало колонок")
                sys.exit(1)

            batch = []
            seen_urls = set()
            for idx, row in enumerate(reader):
                if limit is not None and inserted + skipped >= limit:
                    break
                try:
                    t = row_to_raw(row)
                except Exception as e:
                    logger.debug("Строка %s: %s", idx + 2, e)
                    skipped += 1
                    continue
                if t is None:
                    skipped += 1
                    continue
                url = t[1]
                if url in seen_urls:
                    skipped += 1
                    continue
                seen_urls.add(url)
                batch.append(t)
                if limit is not None and inserted + len(batch) >= limit:
                    batch = batch[: limit - inserted]
                if len(batch) >= batch_size or (limit is not None and inserted + len(batch) >= limit):
                    await conn.executemany(
                        """
                        INSERT INTO raw_vacancies (
                            source, url, title, description, full_text,
                            city, region, region_code,
                            employer, salary_from, salary_to, currency,
                            published_at, raw_data
                        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14::jsonb)
                        """,
                        batch,
                    )
                    inserted += len(batch)
                    logger.info("Вставлено %d записей (всего %d)", len(batch), inserted)
                    batch = []
                    if limit is not None and inserted >= limit:
                        break

            if batch:
                await conn.executemany(
                    """
                    INSERT INTO raw_vacancies (
                        source, url, title, description, full_text,
                        city, region, region_code,
                        employer, salary_from, salary_to, currency,
                        published_at, raw_data
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14::jsonb)
                    """,
                    batch,
                )
                inserted += len(batch)

        logger.info("Готово. Вставлено: %d, пропущено: %d", inserted, skipped)
    finally:
        await conn.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--path", type=Path, default=ROOT / "experiments" / "vacancies.csv")
    parser.add_argument("--limit", type=int, default=None, help="Макс. количество строк")
    args = parser.parse_args()
    asyncio.run(run(args.path, args.limit))


if __name__ == "__main__":
    main()
