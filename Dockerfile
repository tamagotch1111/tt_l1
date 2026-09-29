FROM python:3.11.9-slim

# Создаем пользователя без прав root
RUN groupadd -r appuser && useradd -r -g appuser appuser

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Создаем папку для базы данных и отдаем права безопасному пользователю
RUN mkdir -p data && chown -R appuser:appuser /app

# Переключаемся на безопасного пользователя
USER appuser

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
