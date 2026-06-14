FROM python:3.11-slim

WORKDIR /app

# Instala dependências do sistema necessárias para compilar pacotes se preciso
RUN apt-get update && apt-get install -y --no-install-recommends gcc libpq-dev && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

# Define PYTHONPATH para permitir imports de módulos
ENV PYTHONPATH=/app

CMD ["uvicorn", "APP.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
