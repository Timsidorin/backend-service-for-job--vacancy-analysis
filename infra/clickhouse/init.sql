-- Таблица для аналитики вакансий (OLAP)
-- Денормализованная: raw + processed в одном месте

CREATE DATABASE IF NOT EXISTS vacancies;

CREATE TABLE IF NOT EXISTS vacancies.vacancies_analytics
(
    raw_uuid UUID,
    processed_uuid UUID,
    
    -- raw
    source LowCardinality(String),
    title String,
    description String,
    city LowCardinality(Nullable(String)),
    region LowCardinality(Nullable(String)),
    region_code LowCardinality(Nullable(String)),
    employer String,
    salary_from Nullable(Int32),
    salary_to Nullable(Int32),
    salary_typical Nullable(Int32),
    currency LowCardinality(Nullable(String)),
    published_at Nullable(DateTime64(3)),
    published_date Date MATERIALIZED toDate(published_at),
    
    -- processed
    key_skills Array(String),
    grade LowCardinality(Nullable(String)),
    domain LowCardinality(Nullable(String)),
    processed_at DateTime64(3)
)
ENGINE = MergeTree()
PARTITION BY toYYYYMM(published_date)
ORDER BY (raw_uuid)
SETTINGS index_granularity = 8192;

-- Миграция: добавить domain, если таблица уже существовала без этой колонки
ALTER TABLE vacancies.vacancies_analytics ADD COLUMN IF NOT EXISTS domain LowCardinality(Nullable(String));
