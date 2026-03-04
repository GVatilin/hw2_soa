FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY ./src ./src
COPY ./generated ./generated
COPY ./alembic ./alembic
COPY ./alembic.ini ./alembic.ini

ENV PYTHONPATH=/app:/app/generated/src
CMD ["uvicorn", "src.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
