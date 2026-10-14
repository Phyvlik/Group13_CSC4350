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
