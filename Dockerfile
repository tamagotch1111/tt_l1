FROM python:3.11.9-slim

# Создаем пользователя без прав root
RUN groupadd -r appuser && useradd -r -g appuser appuser
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Создаем пустой .env-файл для библиотеки slowapi и настраиваем права
RUN touch .env && mkdir -p data && chown -R appuser:appuser /app && chmod 777 /app/data

# Переключаемся на безопасного пользователя
USER appuser

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
