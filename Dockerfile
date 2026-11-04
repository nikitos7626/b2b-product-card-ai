FROM python:3.11-slim

WORKDIR /app

# Установка системных зависимостей
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Установка зависимостей Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копирование исходного кода и данных
COPY . .

# Переменные окружения по умолчанию
ENV PYTHONUNBUFFERED=1

EXPOSE 8000

# Запуск FastAPI приложения
CMD ["python", "-m", "app.main"]
