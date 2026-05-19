### Быстрый старт

1. Установить зависимости:
   ```
   uv sync
   ```
2. Скопировать `.env.example` → `.env` и заполнить значения.
3. Применить миграции PostgreSQL:
   ```
   uv run alembic upgrade head
   ```
4. Поднять инфраструктуру (Kafka + ClickHouse):
   ```
   docker compose up -d kafka clickhouse
   ```
5. Запустить сервисы локально:
   - Auth: `uv run python -m services.auth_service.main`
   - Vacancy Analytics: `uv run python -m services.vacancy_analytics_service.main`
   - Vacancy Collector: `uv run python -m services.vacancy_collector_service.main`
   - Vacancy ML: `uv run python -m services.vacancy_ml_service.main`
   - Vacancy Pipeline Worker: `uv run python -m services.vacancy_pipeline_worker.main`
   - API Gateway: `uv run python -m api_gateway.main`
   - Service Manager (опционально): `uv run python -m services.service_manager.main`

При необходимости завершить все процессы Python:
`taskkill /F /IM python.exe`

### Сбор вакансий: batch vs realtime

**Batch (исторический импорт):**
- `scripts/import_vacancies_csv.py` — импорт CSV в `raw_vacancies`.
- `scripts/batch_process_vacancies.py` — заполняет `processed_vacancies`.
- `scripts/backfill_vacancy_embeddings.py` — заполняет эмбеддинги (pgvector).
- `scripts/sync_to_clickhouse.py` — переносит данные в ClickHouse.

**Realtime:**
- **Vacancy Collector Service** периодически запускает коннекторы (HH.ru, Avito) и сохраняет вакансии в `raw_vacancies`.
- **Vacancy Pipeline Worker** слушает Kafka и обрабатывает цепочку:
  - `vacancies.raw` → обработка → `processed_vacancies`
  - `vacancies.processed` → построение эмбеддингов
  - `vacancies.embedded` → синхронизация в ClickHouse

### Порты сервисов

| Сервис | Порт |
|--------|------|
| API Gateway | 8000 |
| Vacancy ML | 8001 |
| Vacancy Analytics | 8002 |
| Vacancy Collector | 8003 |
| Auth | 8005 |
| Service Manager | 8010 |

### Профиль соискателя (PDF) и рекомендации

Через **Vacancy Analytics** (тот же префикс `/api/v1/analytics`, проксируется API Gateway):

| Метод | Путь | Описание |
|-------|------|----------|
| `POST` | `/api/v1/analytics/profile/resume` | Загрузка PDF-резюме (`multipart/form-data`, поле файла). Нужен `Authorization: Bearer`. Текст извлекается из PDF, структурируется через LLM, строится эмбеддинг, данные пишутся в таблицу `candidate_profiles`. |
| `GET` | `/api/v1/analytics/profile` | Текущий сохранённый профиль (JSON навыков, превью текста). |
| `GET` | `/api/v1/analytics/recommendations?source=vk` | Рекомендации по интересам VK (как раньше): нужны `VK_ACCESS_TOKEN` и `vk_id` у пользователя. |
| `GET` | `/api/v1/analytics/recommendations?source=resume` | Рекомендации по профилю из резюме: сначала загрузите PDF через `profile/resume`. Ответ включает `match_percent`, `matched_skills`, `missing_skills`, `vacancy_url`. |

Файлы резюме по умолчанию сохраняются в каталог `uploads/resumes/` (см. `RESUME_UPLOAD_DIR` в конфиге analytics).

Переменные окружения: `OPENAI_API_KEY` (обязательно для загрузки резюме и эмбеддингов), опционально `OPENAI_RESUME_MODEL` (по умолчанию `gpt-4o-mini`).
