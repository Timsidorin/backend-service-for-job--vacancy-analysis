import csv
import pandas as pd
import json
import uuid
from datetime import datetime
import os
import re
import sys
import requests
from pathlib import Path

# =========================================================================
# ⚙️ НАСТРОЙКИ
# =========================================================================
INPUT_FILE = "Raw_Jobs.csv"
OUTPUT_FILE = "raw_vacancies_ready.csv"
CITY_DB_FILE = "russian_cities.csv"

# =========================================================================
# 🗺️ 1. СПРАВОЧНИК ISO КОДОВ (Стандарт ISO 3166-2:RU)
# =========================================================================
REGION_ISO_CODES = {
    "Адыгея": "RU-AD", "Башкортостан": "RU-BA", "Бурятия": "RU-BU", "Алтай": "RU-AL",
    "Дагестан": "RU-DA", "Ингушетия": "RU-IN", "Кабардино-Балкария": "RU-KB",
    "Калмыкия": "RU-KL", "Карачаево-Черкесия": "RU-KC", "Карелия": "RU-KR",
    "Коми": "RU-KO", "Марий Эл": "RU-ME", "Мордовия": "RU-MO", "Саха (Якутия)": "RU-SA",
    "Северная Осетия - Алания": "RU-SE", "Татарстан": "RU-TA", "Тыва": "RU-TY",
    "Удмуртия": "RU-UD", "Хакасия": "RU-KK", "Чечня": "RU-CE", "Чувашия": "RU-CU",
    "Алтайский край": "RU-ALT", "Краснодарский край": "RU-KDA", "Красноярский край": "RU-KYA",
    "Приморский край": "RU-PRI", "Ставропольский край": "RU-STA", "Хабаровский край": "RU-KHA",
    "Амурская область": "RU-AMU", "Архангельская область": "RU-ARK", "Астраханская область": "RU-AST",
    "Белгородская область": "RU-BEL", "Брянская область": "RU-BRY", "Владимирская область": "RU-VLA",
    "Волгоградская область": "RU-VGG", "Вологодская область": "RU-VLG", "Воронежская область": "RU-VOR",
    "Ивановская область": "RU-IVA", "Иркутская область": "RU-IRK", "Калининградская область": "RU-KGD",
    "Калужская область": "RU-KLU", "Камчатский край": "RU-KAM", "Кемеровская область": "RU-KEM",
    "Кировская область": "RU-KIR", "Костромская область": "RU-KOS", "Курганская область": "RU-KGN",
    "Курская область": "RU-KRS", "Ленинградская область": "RU-LEN", "Липецкая область": "RU-LIP",
    "Магаданская область": "RU-MAG", "Московская область": "RU-MOS", "Мурманская область": "RU-MUR",
    "Нижегородская область": "RU-NIZ", "Новгородская область": "RU-NGR", "Новосибирская область": "RU-NVS",
    "Омская область": "RU-OMS", "Оренбургская область": "RU-ORE", "Орловская область": "RU-ORL",
    "Пензенская область": "RU-PNZ", "Пермский край": "RU-PER", "Псковская область": "RU-PSK",
    "Ростовская область": "RU-ROS", "Рязанская область": "RU-RYA", "Самарская область": "RU-SAM",
    "Саратовская область": "RU-SAR", "Сахалинская область": "RU-SAK", "Свердловская область": "RU-SVE",
    "Смоленская область": "RU-SMO", "Тамбовская область": "RU-TAM", "Тверская область": "RU-TVE",
    "Томская область": "RU-TOM", "Тульская область": "RU-TUL", "Тюменская область": "RU-TYU",
    "Ульяновская область": "RU-ULY", "Челябинская область": "RU-CHE", "Забайкальский край": "RU-ZAB",
    "Ярославская область": "RU-YAR", "Москва": "RU-MOW", "Санкт-Петербург": "RU-SPE",
    "Севастополь": "RU-SEV", "Крым": "RU-CR", "Ханты-Мансийский АО": "RU-KHM", "Ямало-Ненецкий АО": "RU-YAN"
}


# =========================================================================
# 📥 2. ЗАГРУЗКА БАЗЫ ГОРОДОВ
# =========================================================================
def load_city_db():
    path = Path(CITY_DB_FILE)
    if not path.exists():
        print("📥 Скачиваю базу городов России...")
        try:
            url = "https://raw.githubusercontent.com/pensnarik/russian-cities/master/russian-cities.json"
            data = requests.get(url).json()
            rows = []
            for item in data:
                city = item.get("name")
                region = item.get("subject")
                if city and region:
                    rows.append({"city": city, "region": region})
            df = pd.DataFrame(rows)
            df.to_csv(path, index=False)
            print(f"✅ База сохранена ({len(df)} городов)")
        except Exception as e:
            print(f"⚠️ Ошибка базы: {e}")
            return {}

    df = pd.read_csv(path)
    city_map = {}
    for _, row in df.iterrows():
        city_clean = str(row['city']).strip().lower()
        region_clean = row['region']

        iso_code = None
        for reg_name, code in REGION_ISO_CODES.items():
            if reg_name.lower() in region_clean.lower():
                iso_code = code
                break
        city_map[city_clean] = (region_clean, iso_code)

    return city_map


CITY_DB = {}


# =========================================================================
# 🔍 3. УМНЫЙ ПОИСК РЕГИОНА
# =========================================================================
def get_region_fast(city_raw):
    """Разбивает адрес 'Уфа, ул. Ленина' -> находит 'Уфа' -> возвращает регион"""
    if pd.isna(city_raw) or not str(city_raw).strip():
        return None, None

    raw_str = str(city_raw).lower().strip()
    parts = [p.strip() for p in raw_str.split(',')]

    for part in parts:
        clean_part = re.sub(r'\b(г\.|город|с\.|село|п\.|поселок)\s*', '', part).strip()

        # 1. Поиск в базе
        if clean_part in CITY_DB:
            return CITY_DB[clean_part]

        # 2. Хардкод популярных
        if "москва" in clean_part: return ("г Москва", "RU-MOW")
        if "петербург" in clean_part or "спб" in clean_part: return ("г Санкт-Петербург", "RU-SPE")
        if "екатеринбург" in clean_part: return ("Свердловская обл", "RU-SVE")
        if "новосибирск" in clean_part: return ("Новосибирская обл", "RU-NVS")
        if "краснодар" in clean_part: return ("Краснодарский край", "RU-KDA")
        if "казань" in clean_part: return ("Респ Татарстан", "RU-TA")
        if "уфа" in clean_part: return ("Респ Башкортостан", "RU-BA")
        if "нижний новгород" in clean_part: return ("Нижегородская обл", "RU-NIZ")
        if "челябинск" in clean_part: return ("Челябинская обл", "RU-CHE")
        if "самара" in clean_part: return ("Самарская обл", "RU-SAM")
        if "ростов" in clean_part: return ("Ростовская обл", "RU-ROS")
        if "воронеж" in clean_part: return ("Воронежская обл", "RU-VOR")
        if "пермь" in clean_part: return ("Пермский край", "RU-PER")
        if "волгоград" in clean_part: return ("Волгоградская обл", "RU-VGG")
        if "саратов" in clean_part: return ("Саратовская обл", "RU-SAR")
        if "тюмень" in clean_part: return ("Тюменская обл", "RU-TYU")
        if "ижевск" in clean_part: return ("Удмуртская Респ", "RU-UD")
        if "барнаул" in clean_part: return ("Алтайский край", "RU-ALT")
        if "иркутск" in clean_part: return ("Иркутская обл", "RU-IRK")
        if "ульяновск" in clean_part: return ("Ульяновская обл", "RU-ULY")
        if "хабаровск" in clean_part: return ("Хабаровский край", "RU-KHA")
        if "владивосток" in clean_part: return ("Приморский край", "RU-PRI")
        if "ярославль" in clean_part: return ("Ярославская обл", "RU-YAR")
        if "махачкала" in clean_part: return ("Респ Дагестан", "RU-DA")
        if "томск" in clean_part: return ("Томская обл", "RU-TOM")
        if "оренбург" in clean_part: return ("Оренбургская обл", "RU-ORE")
        if "кемерово" in clean_part: return ("Кемеровская обл", "RU-KEM")
        if "рязань" in clean_part: return ("Рязанская обл", "RU-RYA")
        if "астрахань" in clean_part: return ("Астраханская обл", "RU-AST")
        if "пенза" in clean_part: return ("Пензенская обл", "RU-PNZ")
        if "липецк" in clean_part: return ("Липецкая обл", "RU-LIP")
        if "тула" in clean_part: return ("Тульская обл", "RU-TUL")
        if "киров" in clean_part: return ("Кировская обл", "RU-KIR")

    return None, None


def parse_salary(s: str):
    if not isinstance(s, str): return None, None, None
    s = s.strip()
    if not s or "не указана" in s.lower(): return None, None, None

    cur_match = re.search(r"([A-Z]{3})", s)
    currency = cur_match.group(1) if cur_match else "RUR"
    nums = re.findall(r"\d+", s.replace(" ", ""))
    nums = [int(n) for n in nums] if nums else []

    if len(nums) == 1:
        return nums[0], None, currency
    elif len(nums) >= 2:
        return nums[0], nums[1], currency
    return None, None, None


# =========================================================================
# 🚀 MAIN
# =========================================================================
def main():
    global CITY_DB
    CITY_DB = load_city_db()

    if not os.path.exists(INPUT_FILE):
        print(f"❌ {INPUT_FILE} не найден")
        return

    print(f"🔄 Читаю {INPUT_FILE}...")
    df = pd.read_csv(INPUT_FILE, delimiter=';', encoding="utf-8-sig")
    print(f"📊 Всего строк: {len(df)}")

    print("💰 Парсим данные (ОФФЛАЙН)...")

    vacancies = []

    for idx, row in df.iterrows():
        vacancy_uuid = str(uuid.uuid4())

        # Безопасное получение полей
        title = row.get("title") or "Unknown"
        desc = row.get("description") or ""
        city = row.get("location") or "Unknown"
        emp = row.get("company") or "Unknown"
        salary_raw = str(row.get("salary", ""))

        salary_from, salary_to, currency = parse_salary(salary_raw)

        # Мгновенный поиск региона
        region, region_code = get_region_fast(city)

        # Очистка данных для JSON (NaN -> None)
        key_skills_val = row.get("key_skills")
        if pd.isna(key_skills_val): key_skills_val = None

        job_type_val = row.get("job_type")
        if pd.isna(job_type_val): job_type_val = None

        experience_val = row.get("experience")
        if pd.isna(experience_val): experience_val = None

        source_type_val = row.get("type")
        if pd.isna(source_type_val): source_type_val = None

        if (idx + 1) % 1000 == 0:
            print(f"   Обработано {idx + 1}/{len(df)}")

        raw_payload = {
            "hh_id": row.get("id"),
            "experience": experience_val,
            "job_type": job_type_val,
            "key_skills": key_skills_val,
            "source_type": source_type_val,
        }

        vacancies.append({
            "uuid": vacancy_uuid,
            "source": "kaggle_raw_jobs",
            "url": f"https://hh.ru/vacancy/{row.get('id')}",
            "title": str(title),
            "description": str(desc),
            "full_text": str(desc),
            "city": str(city),
            "region": region,
            "region_code": region_code,
            "employer": str(emp),
            "salary_from": salary_from,
            "salary_to": salary_to,
            "currency": currency,
            "published_at": row.get("date_of_post"),
            "parsed_at": datetime.now().isoformat(),
            "raw_data": json.dumps(raw_payload, ensure_ascii=False)
        })

    df_out = pd.DataFrame(vacancies)
    # Используем quotechar для корректного экранирования спецсимволов
    df_out.to_csv(OUTPUT_FILE, index=False, encoding="utf-8-sig", quoting=csv.QUOTE_ALL)

    print(f"\n🎉 Готово! {len(df_out)} вакансий в {OUTPUT_FILE}")
    print("\n📋 Примеры:")
    print(df_out[["city", "region", "region_code"]].head(10))
    print(f"\n💾 SQL:\nCOPY raw_vacancies FROM '{os.path.abspath(OUTPUT_FILE)}' DELIMITER ',' CSV HEADER;")


if __name__ == "__main__":
    main()
