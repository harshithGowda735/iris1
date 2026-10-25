# IRIS

IRIS is a privacy-first hierarchical academic communication platform for colleges, departments, batches, and sections.

## Key Features

- **Academic Hierarchy Engine**: Directed acyclic tree (`COLLEGE` -> `DEPARTMENT` -> `BATCH` -> `SECTION`) with recursive CTE traversal for fast breadcrumb navigation.
- **Privacy-First Profiles & RBAC**: Zero phone numbers or private emails exposed. Role-based access control (`MEMBER`, `CR`, `FACULTY`, `ADMIN`) with downward hierarchical inheritance.
- **Content Delivery**:
  - `CHAT`: Ephemeral real-time communication for verified section members.
  - `BOARD`: Official announcement broadcasts strictly restricted to CRs, Faculty, and Admins.
  - `REPO`: Academic materials and lab manuals indexed by subject code.
- **Asynchronous Architecture**: Built on FastAPI, async SQLAlchemy 2.0, asyncpg, and Supabase PostgreSQL.

## Backend Quickstart

### Prerequisites
- Python 3.12+
- Docker & Docker Compose (optional)

### Local Setup
```bash
cd backend
python -m venv .venv
# On Windows:
.venv\Scripts\activate
# On Linux/macOS:
source .venv/bin/activate

pip install -r requirements.txt
```

### Environment Variables
Copy `.env.example` to `.env` and fill in your Supabase database and JWT credentials:
```bash
cp .env.example .env
```

### Running Tests
```bash
pytest
```

### Starting the Server
```bash
uvicorn app.main:app --reload --port 8000
```
API Documentation will be available at `http://127.0.0.1:8000/docs`.
