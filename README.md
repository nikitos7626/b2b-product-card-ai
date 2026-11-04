# B2B Product Card AI Assistant

AI-сервис автоматической генерации и валидации черновиков карточек товаров контрольно-измерительных приборов и автоматики (КИПиА) для B2B интернет-магазина.

**Репозиторий:** [https://github.com/nikitos7626/b2b-product-card-ai](https://github.com/nikitos7626/b2b-product-card-ai)

---

## 🚀 Установка и запуск

### Шаг 1. Клонирование и настройка окружения
```bash
git clone https://github.com/nikitos7626/b2b-product-card-ai.git
cd b2b-product-card-ai
cp .env.example .env
```
В файле `.env` укажите ваш API-ключ Google Gemini:
```ini
GEMINI_API_KEY=ваш_ключ_google_ai_studio
```

---

### Шаг 2. Запуск сервиса

#### Способ 1: Запуск через Docker (Рекомендуемый)
```bash
docker compose up --build
```
Сервис автоматически соберет контейнер и поднимется на `http://localhost:8000`.

#### Способ 2: Локальный запуск на Python
```bash
pip install -r requirements.txt
python -m app.main
```
- **Интерактивный веб-интерфейс:** `http://localhost:8000`
- **Документация Swagger OpenAPI:** `http://localhost:8000/docs`
- **Проверка здоровья (Health-check):** `http://localhost:8000/api/health`

---

## 🧪 Запуск тестов

### Модульные тесты Pytest
```bash
pytest tests/ -v
```
*(11 изолированных тестов: валидация, нормализация ГОСТ, Grounding Verifier, контроллеры, Schema.org. Время выполнения ~0.35 с).*

### Сквозной бенчмарк по 20 категориям
```bash
python test_20_categories.py
```
*(Сквозной интеграционный тест по 20 реальным категориям промышленного каталога с проверкой SEO-лимитов и отсутствия галлюцинаций).*

---

## 📁 Структура проекта и ключевые артефакты

- `app/controllers/` — модульные контроллеры роутов (FastAPI APIRouter).
- `app/core/` — конфигурация приложения (`config.py`) и инженерные промпты (`prompt.py`).
- `app/schemas/` — Pydantic-модели валидации данных (`product.py`).
- `app/services/` — сервис карточек (`card_service.py`), Gemini API клиент (`llm_client.py`), Grounding Verifier и нормализатор ГОСТ (`validator.py`).
- `data/` — датасеты оборудования и таксономия 238 категорий КИПиА (`souz-pribor.ru`).
- `output/` — готовые результаты генерации карточек ([product_1_result.md](output/product_1_result.md), [product_2_result.md](output/product_2_result.md)) и отчёт валидации по 20 категориям.
