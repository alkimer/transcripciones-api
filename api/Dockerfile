FROM python:3.11

WORKDIR /app

COPY . .

# Instalación de dependencias
RUN pip install --no-cache-dir fastapi[all] psycopg2-binary

# Cambio de directorio al que contiene main.py
WORKDIR /app/api

ENV PYTHONPATH=/app

# Ejecutar Uvicorn desde donde está el archivo main.py
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
