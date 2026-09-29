FROM python:3.11-slim

# Задаем рабочую папку внутри контейнера
WORKDIR /app

# Устанавливаем зависимости
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем исходный код
COPY ./app ./app

# Открываем порт 8000 наружу
EXPOSE 8000

# Запускаем веб-сервер
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
