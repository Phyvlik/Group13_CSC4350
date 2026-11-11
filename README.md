# Epoch

Epoch is a trading practice and behavior analyzer built for CSC 4350 Software Engineering (Group 13).

Users replay historical market data with future prices hidden, place paper trades with simulated money, write down their reasoning before the outcome is revealed, and receive feedback on their trading habits based on statistics the backend computes.

## Core Rules

1. **No look-ahead.** The replay endpoint only returns price bars up to the session's current replay position. Future prices never leave the server.
2. **Atomic trades.** Every cash balance and position update happens inside one database transaction, so a trade is never partially applied.
3. **Evidence-based feedback.** Feedback text is only generated from stats the backend computed and verified, never guessed.
4. **Simulation only.** All trading is simulated. There is no real brokerage connection.

## Tech Stack

| Layer    | Technology                                   |
| -------- | -------------------------------------------- |
| Frontend | React, TypeScript, Vite, Lightweight Charts  |
| Backend  | Python, FastAPI, SQLAlchemy, Alembic         |
| Database | PostgreSQL                                   |
| Auth     | JWT, bcrypt                                  |
| Tooling  | Docker, docker-compose                       |

## Team

| Name    | GitHub                                         |
| ------- | ---------------------------------------------- |
| Vivek   | [@Phyvlik](https://github.com/Phyvlik)         |
| Shelden | [@sheldenr](https://github.com/sheldenr)       |
| Corey   | [@corey-rp](https://github.com/corey-rp)       |
| Tej     | [@tejp9230](https://github.com/tejp9230)       |

## Project Status

### Final Sprint: Integration

Every feature branch is merged into `release/integration` and lands on `main` through one integration PR, so the app runs end to end: sign up or sign in, start a replay session, step through bars, place paper trades, and view statistics. Admins manage users and datasets.

| Feature | Branch / PR | Owner |
| ------- | ----------- | ----- |
| Database schema and replay engine | `feature/replay-engine` (#22) | Shelden |
| Paper trading | `feature/paper-trading` | Shelden |
| Auth (register, login, profile) | `feature/6-auth` (#19) | Vivek |
| Market data import from Twelve Data | `feature/7-market-data` (#21) | Vivek |
| Statistics | `feature/12-stats` (#17) | Tej |
| Frontend pages and replay chart | `feature/10-react-pages` (#18) | Corey |
| Frontend tests | `feature/10-frontend-tests` | Corey |
| API contract and README status | `docs/api-contract` (#20), `docs/readme-status` (#14) | Vivek |
| One shared auth, admin users and datasets, chunked import, demo seed, CI, frontend wired to the API | `release/integration` | Vivek |

Not built yet (the frontend shows a clear TODO): saving trade reasoning to the journal (#11), behavior feedback (#13), and CSV dataset upload.

### Sprint 1: Done (by Vivek)

- Repo setup, README, and [CONTRIBUTING.md](CONTRIBUTING.md) (on `main`)
- Branch protection: `main` requires a pull request with 3 approvals
- [PR #1](https://github.com/Phyvlik/Group13_CSC4350/pull/1): Docker setup (`docker-compose.yml` with Postgres, backend, and frontend, plus `.env.example`)
- [PR #2](https://github.com/Phyvlik/Group13_CSC4350/pull/2): FastAPI backend skeleton with a `/health` endpoint
- [PR #3](https://github.com/Phyvlik/Group13_CSC4350/pull/3): Database schema from our ERD (12 tables, Alembic migration)
- [PR #4](https://github.com/Phyvlik/Group13_CSC4350/pull/4): React + TypeScript frontend skeleton with page stubs
- [PR #5](https://github.com/Phyvlik/Group13_CSC4350/pull/5): Requirements doc in [docs/requirements.md](docs/requirements.md)

> **Note:** PRs #1 to #5 are waiting on approvals. PR #2 must merge before PR #3, because #3 is built on top of #2.

### Sprint 1: Teammate Tasks

| Teammate | Tasks |
| -------- | ----- |
| Shelden  | Approve PRs #1 to #5, then start the replay engine ([#8](https://github.com/Phyvlik/Group13_CSC4350/issues/8)) |
| Corey    | Accept the repo invite, approve PRs #1 to #5, then start the frontend pages ([#10](https://github.com/Phyvlik/Group13_CSC4350/issues/10)) |
| Tej      | Accept the repo invite, approve PRs #1 to #5, then start stats ([#12](https://github.com/Phyvlik/Group13_CSC4350/issues/12)) |

### Who Owns What

| Feature | Issue | Owner | Depends on |
| ------- | ----- | ----- | ---------- |
| Auth | [#6](https://github.com/Phyvlik/Group13_CSC4350/issues/6) | Vivek | None |
| Market data import | [#7](https://github.com/Phyvlik/Group13_CSC4350/issues/7) | Vivek | None |
| Replay engine | [#8](https://github.com/Phyvlik/Group13_CSC4350/issues/8) | Shelden | Auth, Market data import |
| Paper trading | [#9](https://github.com/Phyvlik/Group13_CSC4350/issues/9) | Shelden | Replay engine |
| Frontend pages + replay chart | [#10](https://github.com/Phyvlik/Group13_CSC4350/issues/10) | Corey | None to start |
| Trade journal | [#11](https://github.com/Phyvlik/Group13_CSC4350/issues/11) | Corey | Paper trading |
| Stats | [#12](https://github.com/Phyvlik/Group13_CSC4350/issues/12) | Tej | Paper trading |
| Behavior feedback | [#13](https://github.com/Phyvlik/Group13_CSC4350/issues/13) | Tej | Stats |
| Admin user management | FR-21 (no issue yet) | Vivek | Auth |
| Admin dataset management | FR-20 (no issue yet) | Vivek | Market data import |

### How to Start Your Task

1. Accept the repo invite (check your email or [github.com/notifications](https://github.com/notifications)).
2. Clone the repo:
   ```bash
   git clone https://github.com/Phyvlik/Group13_CSC4350.git
   cd Group13_CSC4350
   ```
3. Pull the latest `main`:
   ```bash
   git checkout main
   git pull origin main
   ```
4. Make a branch named `feature/<issue-number>-<short-name>`:
   ```bash
   git checkout -b feature/8-replay-engine
   ```
5. Commit in small steps with `type: description` messages (types: `feat`, `fix`, `chore`, `docs`):
   ```bash
   git commit -m "feat: add session start endpoint"
   ```
6. Push your branch:
   ```bash
   git push -u origin feature/8-replay-engine
   ```
7. Open a PR into `main`, and link the issue in the PR description with `Closes #<number>` (for example, `Closes #8`).
8. Get 3 approvals, then merge.

## Setup

### Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (includes docker compose)
- Git
- Optional for running outside Docker or running tests: Python 3.12+, Node.js 24, and PostgreSQL 16

### 1. Clone and configure

```bash
git clone https://github.com/Phyvlik/Group13_CSC4350.git
cd Group13_CSC4350
cp .env.example .env
```

Edit `.env`:

- `JWT_SECRET_KEY`: set a long random value, for example the output of `python -c "import secrets; print(secrets.token_urlsafe(48))"`.
- `TWELVE_DATA_API_KEY`: optional. Only needed to import real market data (free key at [twelvedata.com](https://twelvedata.com/)).
- `VITE_API_URL`: where the browser reaches the backend. The default `http://localhost:8000` works with docker compose.

Never commit `.env`.

### 2. Start everything

```bash
docker compose up --build
```

The backend container runs `alembic upgrade head` before it starts, so the database schema is always current. Once running:

- Frontend: http://localhost:5173
- Backend API: http://localhost:8000
- API docs (Swagger): http://localhost:8000/docs
- Health check: http://localhost:8000/health (reports `"database": "ok"` when Postgres is reachable)

### 3. Create an admin

In a second terminal:

```bash
docker compose exec backend python scripts/create_admin.py --email you@example.com --name "Your Name"
```

It prompts for a password (8+ characters). Running it with an existing email promotes that account to admin instead. Traders sign up from the frontend.

### 4. Load market data

Pick one:

- **Demo data (no API key needed):**
  ```bash
  docker compose exec backend python scripts/seed_demo.py
  ```
  This creates a `DEMO` instrument with 500 generated daily bars (2023 to 2024), a demo trader `demo@epoch.test` / `demo-password`, and a demo admin `admin@epoch.test` / `admin-password`. It is safe to run more than once.

- **Real data from Twelve Data:** set `TWELVE_DATA_API_KEY` in `.env`, restart the backend, sign in as an admin, and call the import endpoint (Swagger at http://localhost:8000/docs works too):
  ```bash
  curl -X POST http://localhost:8000/admin/market-data/import \
    -H "Authorization: Bearer <admin access_token>" \
    -H "Content-Type: application/json" \
    -d '{"symbol": "AAPL", "exchange": "NASDAQ", "interval": "1day", "start": "2023-01-02T00:00:00Z", "end": "2024-12-31T00:00:00Z"}'
  ```
  Ranges over 5000 bars are fetched in several requests automatically. The frontend chart works best with `1day` data.

Then open http://localhost:5173, sign in, and start a practice session.

### 5. Run the tests

Backend (uses an in-memory SQLite database, no Postgres needed):

```bash
cd backend
python -m venv .venv
source .venv/bin/activate    # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
pytest
```

Frontend:

```bash
cd frontend
npm ci
npm test          # vitest
npm run build     # TypeScript check and production build
```

GitHub Actions runs both on every pull request and on every push to `main` ([.github/workflows/ci.yml](.github/workflows/ci.yml)).

### Run without Docker

Start PostgreSQL yourself and point `DATABASE_URL` in `backend/.env` (or your shell) at it, for example `postgresql+psycopg://epoch:epoch_dev_password@localhost:5432/epoch`. Then:

```bash
cd backend
source .venv/bin/activate
alembic upgrade head
python scripts/create_admin.py --email you@example.com
python scripts/seed_demo.py
uvicorn app.main:app --reload
```

```bash
cd frontend
npm install
npm run dev
```

### API reference

Every endpoint is documented in [docs/api.md](docs/api.md).

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for our branch and pull request workflow.
