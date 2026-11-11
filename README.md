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
| Admin user management | FR-21 (no issue yet) | Unassigned | Auth |

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

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (includes docker-compose)
- Git
- Optional for running outside Docker: Python 3.12+ and Node.js 20+

### Run with Docker

```bash
git clone https://github.com/Phyvlik/Group13_CSC4350.git
cd Group13_CSC4350
cp .env.example .env        # then edit values if needed
docker compose up --build
```

Once running:

- Frontend: http://localhost:5173
- Backend API: http://localhost:8000
- API docs (Swagger): http://localhost:8000/docs
- Health check: http://localhost:8000/health

### Apply database migrations

```bash
docker compose exec backend alembic upgrade head
```

### Run without Docker

Backend:

```bash
cd backend
python -m venv .venv
source .venv/bin/activate    # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Frontend:

```bash
cd frontend
npm install
npm run dev
```

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for our branch and pull request workflow.
