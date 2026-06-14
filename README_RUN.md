# Como rodar o projeto

## Requisitos

- Python 3.11+
- Docker e Docker Compose (opcional, mas recomendado)

## Método recomendado: Docker Compose

No diretório do projeto:

```bash
cd "/Users/ricardo/Documents/Meu projeto"
docker compose up --build
```

A API ficará disponível em:

- http://localhost:8000
- http://localhost:8000/docs

## Método local com Python

```bash
cd "/Users/ricardo/Documents/Meu projeto"
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn APP.main:app --host 0.0.0.0 --port 8000 --reload
```

### Observações

- O app irá criar as tabelas automaticamente no primeiro startup.
- Se você usar Docker Compose, o banco PostgreSQL e a API serão iniciados juntos.
- Se quiser, posso ajudar a gerar um script `docker-compose.override.yml` ou adicionar um `Makefile`.