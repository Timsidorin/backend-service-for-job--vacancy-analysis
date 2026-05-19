#!/usr/bin/env python3
"""
Rule-based определение домена вакансии по навыкам.

Домены: IT, Продажи, Производство, Офис/Бухгалтерия, Медицина, Строительство,
        Логистика, Красота/Услуги, Образование, Другое.

Запуск:
  uv run python -m experiments.rule_based_domains [--sample 50000] [--output domains.png]
"""

import argparse
import asyncio
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except ImportError:
    pass

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

PG_HOST = os.getenv("DB_HOST", "localhost")
PG_PORT = int(os.getenv("DB_PORT", "5432"))
PG_USER = os.getenv("DATABASE_USERNAME", "postgres")
PG_PASS = os.getenv("DATABASE_PASSWORD", "admin")
PG_NAME = os.getenv("DATABASE_NAME", "job_vacancy")

# Правила: домен -> ключевые слова (lowercase). Порядок важен: первый матч выигрывает.
# Последние домены — более общие, чтобы охватить все вакансии.
DOMAIN_RULES = [
    # --- Специфичные домены (высокий приоритет) ---
    ("IT", [
        "python", "java", "javascript", "typescript", "sql", "docker", "kubernetes", "react", "vue", "angular",
        "git", "linux", "backend", "frontend", "программист", "разработчик", "devops", "qa ", "тестировщик",
        "php", "c#", "c++", "golang", "scala", "kotlin", "node", "postgresql", "redis", "mysql", "mongodb",
        "kafka", "jenkins", "ansible", "terraform", "api", "rest", "swift", "ios", "android",
    ]),
    ("Медицина", [
        "медицинск", "врач", "медсестр", "фармаци", "лекарствен", "клиническ", "диагностик",
        "стоматолог", "терапевт", "хирург", "педиатр", "лаборатор", "анализ кров", "меддокументац",
    ]),
    ("Строительство", [
        "строительств", "ремонт", "отделк", "монтаж", "проектирован", "смет", "инженер-строитель",
        "электромонтаж", "сантехник", "отопление", "вентиляция", "маляр", "штукатур",
    ]),
    ("Производство", [
        "производств", "станки", "чпу", "cnc", "металлообработк", "сварк", "токар", "фрезер",
        "autocad", "компас", "solidworks", "чертеж", "технолог", "контроль качества",
        "gmp", "good manufacturing", "цех", "оборудовани", "литей", "сборк", "упаковк",
    ]),
    ("Продажи", [
        "продаж", "активные продажи", "b2b", "b2c", "мерчандайзинг", "мерчендайзинг",
        "развитие продаж", "менеджер по продажам", "коммерческ", "выкладка товар",
        "торговый представитель", "холодные звонки", "взыскание задолженност",
        "активные продажи", "розничн", "оптов",
    ]),
    ("Офис/Бухгалтерия", [
        "1с", "1c", "бухгалтер", "документооборот", "кадра", "зарплата", "делопроизводство",
        "ms office", "excel", "word", "powerpoint", "ворд", "эксель", "офис-менеджер",
        "секретарь", "администратор офиса", "электронный документооборот", "первичн",
    ]),
    ("Логистика", [
        "логистик", "склад", "доставк", "экспедитор", "водитель", "грузчик", "кладовщик",
        "транспорт", "wms", "маршрутизац", "таможен", "приёмк", "приемк", "инвентаризац",
    ]),
    ("Красота/Услуги", [
        "маникюр", "педикюр", "парикмахер", "косметолог", "визажист", "массаж",
        "наращивание ногтей", "стрижк", "окрашивание", "обертыван",
    ]),
    ("Образование", [
        "преподаван", "обучени", "образован", "педагог", "учитель", "репетитор",
        "тренер", "курс", "методик", "воспитатель",
    ]),
    ("Общепит", [
        "повар", "кухн", "ресторан", "кафе", "бар", "общепит", "официант", "повар-кулинар",
        "технолог общественного питания", "повар-кондитер",
    ]),
    ("Охрана/Безопасность", [
        "охрана", "охранник", "сторож", "безопасност", "вч ", "чоп",
    ]),
    ("Маркетинг/Реклама", [
        "маркетинг", "реклам", "smm", "таргет", "контекстн", "коперайт", "brand",
        "digital", "seo", "медиабаинг",
    ]),
    ("HR/Рекрутинг", [
        "подбор персонала", "рекрутер", "hr ", "кадров", "адаптац", "оценка персонала",
    ]),
    ("Юриспруденция", [
        "юрист", "юридическ", "правов", "договор", "претензи", "арбитраж",
    ]),
    ("Финансы/Аудит", [
        "финансы", "аудит", "экономист", "инвестици", "банк", "бюджет", "планирован",
    ]),
    ("Дизайн", [
        "дизайн", "figma", "photoshop", "иллюстратор", "графическ", "верстк", "ui ", "ux ",
    ]),
    ("Торговля/Ритейл", [
        "торговл", "ритейл", "продавец", "кассир", "консультант", "мерчандайзер",
        "торговый зал", "выкладка", "инкассац",
    ]),
    ("Недвижимость", [
        "недвижимост", "риелтор", "агент по недвижимости", "аренд", "загородн",
    ]),
    ("ЖКХ/Коммунальные", [
        "жкх", "коммунальн", "управляющ", "энерго", "теплосет",
    ]),
    ("Сельское хозяйство", [
        "агроном", "сельскохозяйств", "ферм", "животновод", "растениевод",
    ]),
    ("Гостиничный бизнес", [
        "гостиниц", "отель", "администратор гостиницы", "горничная",
    ]),
    ("Сервис/Клиентский сервис", [
        "клиентский сервис", "обслуживание клиентов", "колл-центр", "call center",
        "консультирован", "поддержк клиент",
    ]),
    ("Архитектура/Проектирование", [
        "архитект", "проектирован", "gen", "проект",
    ]),
    ("Аналитика/Данные", [
        "аналитик", "данн", "bi ", "power bi", "tableau", "etl", "дата сайнс",
    ]),
    # --- Широкие домены (всегда в конце) ---
    ("Торговля/Склад", [
        "склад", "торговл", "приём", "прием", "товар", "ассортимент",
    ]),
    ("Рабочие специальности", [
        "слесар", "электрик", "механик", "наладчик", "оператор", "аппаратчик",
    ]),
    ("Управление/Руководство", [
        "руководство", "управление персоналом", "тимлид", "директор", "начальник",
    ]),
    ("Работа с документами", [
        "документ", "отчетност", "ведение документации", "договор",
    ]),
    ("Работа с людьми", [
        "работа с людьми", "коммуникац", "переговор", "клиент", "заказчик",
    ]),
    # --- Общий fallback: мягкие навыки, которые есть почти везде ---
    ("Общие/Универсальные", [
        "работа в команде", "пользователь пк", "коммуникабельность", "ответственность",
        "грамотная речь", "деловое общение", "опытный пользователь пк", "знание пк",
        "умение работать", "мобильность", "стрессоустойчивость", "многозадачность",
        "клиентоориентированность", "навык", "работа на компьютере", "офис",
    ]),
]


def extract_key_skills(skills_val):
    if skills_val is None:
        return []
    if isinstance(skills_val, dict):
        ks = skills_val.get("key_skills", [])
    elif isinstance(skills_val, str):
        try:
            data = json.loads(skills_val)
            ks = data.get("key_skills", [])
        except json.JSONDecodeError:
            return []
    else:
        return []
    return [str(s).lower() for s in (ks if isinstance(ks, list) else [])]


def assign_domain(skills: list[str]) -> str:
    """Присваивает домен по первому совпавшему правилу. Всегда возвращает домен (без «Другое»)."""
    text = " ".join(skills)
    for domain, keywords in DOMAIN_RULES:
        for kw in keywords:
            if kw in text:
                return domain
    return "Общие/Универсальные"


async def load_vacancies(sample_size: int | None):
    try:
        import asyncpg
    except ImportError:
        print("Требуется asyncpg")
        sys.exit(1)

    conn = await asyncpg.connect(
        f"postgresql://{PG_USER}:{PG_PASS}@{PG_HOST}:{PG_PORT}/{PG_NAME}"
    )
    query = """
        SELECT raw_vacancy_uuid, skills
        FROM processed_vacancies
        WHERE skills != '{}'::jsonb
          AND jsonb_array_length(COALESCE(skills->'key_skills', '[]'::jsonb)) > 0
    """
    params = []
    if sample_size:
        query += " ORDER BY random() LIMIT $1"
        params.append(sample_size)
    rows = await conn.fetch(query, *params)
    await conn.close()

    return [
        {"uuid": str(r["raw_vacancy_uuid"]), "skills": extract_key_skills(r["skills"])}
        for r in rows
        if extract_key_skills(r["skills"])
    ]


def visualize_distribution(domain_counts: dict, output_path: Path):
    domains = list(domain_counts.keys())
    counts = list(domain_counts.values())
    colors = plt.cm.Set3(np.linspace(0, 1, len(domains)))

    fig, ax = plt.subplots(figsize=(12, 7))
    bars = ax.barh(domains, counts, color=colors)
    ax.set_xlabel("Количество вакансий")
    ax.set_title("Распределение вакансий по доменам (rule-based)")
    ax.invert_yaxis()

    for bar, cnt in zip(bars, counts):
        pct = 100 * cnt / sum(counts)
        ax.text(bar.get_width() + max(counts) * 0.01, bar.get_y() + bar.get_height() / 2,
                f"{cnt:,} ({pct:.1f}%)", va="center", fontsize=10)

    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"График сохранён: {output_path}")


async def main_async(sample_size: int | None = None, output: str = "domains.png"):
    print("Загрузка вакансий...")
    vacancies = await load_vacancies(sample_size)
    print(f"Загружено {len(vacancies)} вакансий с навыками")

    print("Классификация по доменам...")
    domain_counts: dict[str, int] = {}
    for v in vacancies:
        domain = assign_domain(v["skills"])
        domain_counts[domain] = domain_counts.get(domain, 0) + 1

    # Сортируем по убыванию
    domain_counts = dict(sorted(domain_counts.items(), key=lambda x: -x[1]))

    print("\n--- Распределение по доменам ---\n")
    total = sum(domain_counts.values())
    for domain, cnt in domain_counts.items():
        pct = 100 * cnt / total
        print(f"  {domain}: {cnt:,} ({pct:.1f}%)")

    out_path = ROOT / "experiments" / output
    out_path.parent.mkdir(parents=True, exist_ok=True)
    visualize_distribution(domain_counts, out_path)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--sample", type=int, default=0, help="Размер выборки (0 = все вакансии)")
    parser.add_argument("--output", default="domains.png")
    args = parser.parse_args()
    sample = None if args.sample <= 0 else args.sample
    asyncio.run(main_async(sample_size=sample, output=args.output))


if __name__ == "__main__":
    main()
