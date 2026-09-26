# Railway Task API

A small FastAPI + PostgreSQL project for learning deployment with Railway.

## Stack

- Python
- FastAPI
- SQLAlchemy
- PostgreSQL
- Docker

## API

- `GET /health`
- `GET /tasks`
- `POST /tasks`
- `GET /tasks/{id}`
- `PATCH /tasks/{id}`
- `DELETE /tasks/{id}`
- `GET /docs`

## Run locally

Create a virtual environment and install dependencies:

```bash
python -m venv .venv
```

Windows PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

For local PostgreSQL, set:

```powershell
$env:DATABASE_URL="postgresql://postgres:postgres@localhost:5432/tasks"
```

Then:

```powershell
uvicorn app.main:app --reload
```

Without `DATABASE_URL`, the app falls back to a local SQLite database for quick experiments.

## Railway

1. Create a Railway project.
2. Deploy this GitHub repository as a service.
3. Add a PostgreSQL service to the same Railway project.
4. In the API service, add a reference variable:
   `DATABASE_URL=${{Postgres.DATABASE_URL}}`
   (use your actual PostgreSQL service name if it differs).
5. Generate a public domain for the API service.
6. Open `/docs`.

Railway detects the root `Dockerfile` automatically.
