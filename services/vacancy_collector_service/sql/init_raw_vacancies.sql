
CREATE TABLE IF NOT EXISTS raw_vacancies (
    uuid UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source VARCHAR(50) NOT NULL,
    url VARCHAR NOT NULL,
    title VARCHAR NOT NULL,
    description VARCHAR,
    employer VARCHAR,
    salary_from INTEGER,
    salary_to INTEGER,
    currency VARCHAR(10),
    published_at TIMESTAMP WITH TIME ZONE,
    parsed_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
    raw_data JSONB NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_raw_vacancies_source ON raw_vacancies (source);
