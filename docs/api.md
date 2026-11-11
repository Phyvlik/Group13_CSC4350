# Epoch API Contract

This is the single reference for every backend endpoint the frontend can call. It is written from the code on these branches as of 2026-10-29:

| Area | Branch | PR |
|---|---|---|
| Health | `main` | merged |
| Auth | `feature/6-auth` | #19 |
| Datasets, replay sessions, trade outcomes | `feature/replay-engine` | not opened yet |
| Statistics | `feature/12-stats` | #17 |

If an endpoint changes in one of those branches, update this file in the same PR.

## Authentication

Protected endpoints take a JWT access token in the `Authorization` header:

```
Authorization: Bearer <access_token>
```

- Get a token from `POST /auth/register` or `POST /auth/login` (the `access_token` field).
- Tokens are signed with HS256 using `JWT_SECRET_KEY`. Claims: `sub` (user id as a UUID string), `iat`, and `exp` (default 60 minutes, set by `JWT_ACCESS_TOKEN_EXPIRE_MINUTES`). There is no refresh token yet, so the client logs in again when it expires.
- A missing, malformed, or expired token, or a user that is not `ACTIVE`, returns **401** with `WWW-Authenticate: Bearer`.
- **Dev only:** the shared `get_current_user` dependency also accepts an `X-User-Id: <uuid>` header when no Bearer token is sent. It will be removed before release. Do not use it in frontend code. The statistics endpoints do not accept it.
- The statistics endpoints use their own token check (`stats_auth.py`) until it is merged with the shared one. It also returns **503** if `JWT_SECRET_KEY` is still the template value or shorter than 32 bytes. Set a real secret in `.env` locally.

## Conventions

- Request and response bodies are JSON.
- IDs are UUID strings.
- Timestamps are ISO 8601 in UTC, for example `2026-10-29T14:30:00Z`.
- Prices, cash, quantities, and ratios are decimal **strings** (for example `"150.250000"`), not floats.
- Errors use FastAPI's shape: `{ "detail": "message" }`. Validation errors (**422**) return `detail` as a list of field errors.
- **422** can come back from any endpoint that takes a body, query parameter, or UUID path parameter when the input fails validation. The tables below only list it where it carries a specific meaning.

### Shared types

**User**

```json
{
  "id": "6792648b-cfd4-4d8a-a414-77f9b580eb37",
  "name": "Ada Lovelace",
  "email": "ada@example.com",
  "role": "Trader",
  "status": "Active"
}
```

`role` is `"Trader"` or `"Admin"`. `status` is `"Active"` or `"Disabled"` (any non-active account). This matches the `User` type in `frontend/src/auth.tsx`. `password_hash` is never returned.

**Session**

```json
{
  "session_id": "uuid",
  "user_id": "uuid",
  "dataset_id": "uuid",
  "period_start": "2024-01-01T10:00:00Z",
  "period_end": "2024-01-01T16:00:00Z",
  "replay_at": "2024-01-01T10:00:00Z",
  "replay_speed": "1.00",
  "initial_cash": "10000.00",
  "cash_balance": "10000.00",
  "position_quantity": "0",
  "average_cost": "0",
  "status": "ACTIVE",
  "started_at": "2026-10-29T14:30:00Z",
  "ended_at": null
}
```

`status` is one of `ACTIVE`, `PAUSED`, `COMPLETED`, `ABANDONED`.

**PriceBar**

```json
{
  "bar_id": "uuid",
  "dataset_id": "uuid",
  "bar_at": "2024-01-01T10:00:00Z",
  "open_price": "150.000000",
  "high_price": "150.500000",
  "low_price": "149.500000",
  "close_price": "150.250000",
  "volume": "1000.000000"
}
```

---

## Health

### GET /health

| | |
|---|---|
| Auth | No |
| Request body | None |
| Response 200 | `{ "status": "ok", "database": "ok" }`. `database` is `"unavailable"` if the database cannot be reached; the endpoint still returns 200. |
| Errors | None |

---

## Auth

### POST /auth/register

Creates a trader account and signs it in.

| | |
|---|---|
| Auth | No |
| Request body | `{ "email": "ada@example.com", "password": "at-least-8-chars", "display_name": "Ada" }` |
| Response 201 | `{ "user": User, "access_token": "<jwt>", "token_type": "bearer" }` |

- `email` is trimmed and stored lowercase. Must look like `name@domain.tld`.
- `password` is 8 characters minimum, 72 bytes maximum (bcrypt limit).
- `display_name` is 1 to 100 characters after trimming.
- New accounts are always `Trader`. Admin accounts cannot be self-registered.

| Error | When |
|---|---|
| 409 | Email is already registered (case-insensitive) |
| 422 | Invalid email, password too short or too long, blank display_name |

### POST /auth/login

| | |
|---|---|
| Auth | No |
| Request body | `{ "email": "ada@example.com", "password": "..." }` |
| Response 200 | `{ "user": User, "access_token": "<jwt>", "token_type": "bearer" }` |

| Error | When |
|---|---|
| 401 | Unknown email, wrong password, or the account is not active. The message is the same in all three cases. |

### GET /auth/me

| | |
|---|---|
| Auth | Bearer |
| Request body | None |
| Response 200 | `User` |

| Error | When |
|---|---|
| 401 | Missing or invalid token, or the user is not active |

### PATCH /auth/me

Updates the signed in user. Send at least one of `display_name` or `password`.

| | |
|---|---|
| Auth | Bearer |
| Request body | `{ "display_name": "New Name" }` and/or `{ "password": "new-password", "current_password": "old-password" }` |
| Response 200 | Updated `User` |

| Error | When |
|---|---|
| 400 | `current_password` is wrong |
| 401 | Missing or invalid token |
| 422 | Empty body, `password` sent without `current_password`, new password under 8 characters, blank display_name |

---

## Datasets and replay sessions

All endpoints in this section require a Bearer token. Sessions and trades are scoped to the signed in user: another user's session or trade returns **404**, the same as one that does not exist.

### GET /datasets

Lists the market datasets available to replay.

| | |
|---|---|
| Auth | Bearer |
| Request body | None |
| Response 200 | Array of datasets |

```json
[
  {
    "dataset_id": "uuid",
    "instrument_id": "uuid",
    "provider": "twelvedata",
    "interval": "1min",
    "version": "v1",
    "range_start": "2024-01-01T10:00:00Z",
    "range_end": "2024-01-01T16:00:00Z",
    "imported_at": "2026-10-29T14:30:00Z",
    "instrument": {
      "instrument_id": "uuid",
      "symbol": "AAPL",
      "exchange": "NASDAQ",
      "name": "Apple Inc.",
      "quote_currency": "USD"
    }
  }
]
```

| Error | When |
|---|---|
| 401 | Missing or invalid token |

### POST /sessions

Starts a replay session. `replay_at` starts at `period_start`.

| | |
|---|---|
| Auth | Bearer |
| Request body | `{ "dataset_id": "uuid", "period_start": "datetime", "period_end": "datetime", "initial_cash": "10000.00" }`. `initial_cash` is optional (default 10000.00) and must be greater than 0. Datetimes without a timezone are treated as UTC. |
| Response 201 | `Session` |

| Error | When |
|---|---|
| 400 | `period_start` is not before `period_end` |
| 401 | Missing or invalid token |
| 404 | Dataset not found |
| 422 | `initial_cash` is 0 or negative, or a field is missing or malformed |

### GET /sessions/{id}

| | |
|---|---|
| Auth | Bearer |
| Request body | None |
| Response 200 | `Session` |

| Error | When |
|---|---|
| 401 | Missing or invalid token |
| 404 | Session not found or owned by another user |

### GET /sessions/{id}/bars

Returns bars for the session's dataset up to and including `replay_at`, oldest first. Bars after `replay_at` are never returned (filtered in SQL).

| | |
|---|---|
| Auth | Bearer |
| Query params | `start_at` (optional datetime, only bars at or after this time), `limit` (optional int) |
| Request body | None |
| Response 200 | Array of `PriceBar` |

| Error | When |
|---|---|
| 401 | Missing or invalid token |
| 404 | Session not found or owned by another user |

### POST /sessions/{id}/step

Moves `replay_at` forward by N bars. It never moves past `period_end`; if there are no more bars, the session is returned unchanged.

| | |
|---|---|
| Auth | Bearer |
| Request body | Optional. `{ "count": 1 }`. `bars` and `steps` are accepted as aliases for `count`. Defaults to 1. |
| Response 200 | Updated `Session` |

| Error | When |
|---|---|
| 400 | Session is `COMPLETED` or `ABANDONED` |
| 401 | Missing or invalid token |
| 404 | Session not found or owned by another user |
| 422 | `count` is less than 1 |

### PATCH /sessions/{id}

Changes replay speed, pauses, resumes, or ends a session. All fields are optional.

| | |
|---|---|
| Auth | Bearer |
| Request body | `{ "replay_speed": "2.0", "status": "PAUSED", "ended_at": "datetime" }` |
| Response 200 | Updated `Session` |

- `status` to `COMPLETED` or `ABANDONED` sets `ended_at` (to the given value, or now).
- `status` to `ACTIVE` clears `ended_at`, so an ended session can be resumed.
- Sending only `ended_at` on an `ACTIVE` session marks it `COMPLETED`.

| Error | When |
|---|---|
| 401 | Missing or invalid token |
| 404 | Session not found or owned by another user |
| 422 | `replay_speed` is 0 or negative, or `status` is not a valid value |

### GET /trades/{id}/outcome

Reveals the price movement after a trade. The trade must have a journal entry first. The first successful call sets `outcome_revealed_at`.

| | |
|---|---|
| Auth | Bearer |
| Request body | None |
| Response 200 | See below |

```json
{
  "trade_id": "uuid",
  "session_id": "uuid",
  "placed_at": "2024-01-01T10:02:00Z",
  "side": "BUY",
  "execution_price": "152.000000",
  "quantity": "10.000000",
  "outcome_revealed_at": "2026-10-29T14:35:00Z",
  "next_bar": PriceBar,
  "next_price": "153.250000",
  "price_change": "1.250000",
  "price_change_pct": "0.82236842105263157894736842105"
}
```

`next_bar`, `next_price`, `price_change`, and `price_change_pct` are `null` when there is no later bar. `side` is `BUY` or `SELL`. `price_change_pct` is a percentage (0.82 means 0.82%).

| Error | When |
|---|---|
| 401 | Missing or invalid token |
| 404 | Trade not found or in another user's session |
| 409 | The trade has no journal entry yet |

---

## Statistics

All endpoints in this section require a Bearer token and do not accept `X-User-Id`. Values are decimal strings and can be `null` when a metric is undefined (for example no closed trades).

### POST /sessions/{session_id}/stats/recompute

Calculates, verifies, and saves a new statistics revision for the session.

| | |
|---|---|
| Auth | Bearer |
| Request body | None |
| Response 200 | `SessionStats` (below) |

```json
{
  "session_id": "uuid",
  "quote_currency": "USD",
  "revision": 1,
  "computed_at": "2026-10-29T23:30:00Z",
  "verified_at": "2026-10-29T23:30:00.001Z",
  "calculation_version": "1-proposed",
  "pnl": "18.500000",
  "win_rate": "1.000000",
  "exposure_ratio": "0.200000"
}
```

`win_rate` and `exposure_ratio` are between 0 and 1, or `null`.

| Error | When |
|---|---|
| 401 | Missing or invalid token, or the user is not active |
| 404 | Session not found or owned by another user |
| 409 | Session data cannot produce valid statistics, or a concurrent change conflicted. Retry after resolving. |
| 503 | Token verification is not configured (see Authentication) or the database is unavailable |

### GET /sessions/{session_id}/stats

Returns the latest saved, verified revision. This is a snapshot as of `computed_at`. It does not recompute.

| | |
|---|---|
| Auth | Bearer |
| Request body | None |
| Response 200 | `SessionStats` |

| Error | When |
|---|---|
| 401 | Missing or invalid token, or the user is not active |
| 404 | Session not found or owned by another user |
| 409 | No verified statistics yet. Call `POST .../stats/recompute` first. |
| 503 | Token verification is not configured or the database is unavailable |

### GET /stats/summary

Current totals across all of the user's sessions, grouped by quote currency. Currencies are never combined. A user with no sessions gets `{ "currencies": [] }`.

| | |
|---|---|
| Auth | Bearer |
| Request body | None |
| Response 200 | See below |

```json
{
  "currencies": [
    {
      "quote_currency": "USD",
      "session_count": 2,
      "pnl": "15.000000",
      "win_rate": "0.5",
      "closed_trades": 2,
      "winning_trades": 1,
      "position_value": "2000.000000000000",
      "equity": "20000.000000000000",
      "exposure_ratio": "0.1"
    }
  ]
}
```

| Error | When |
|---|---|
| 401 | Missing or invalid token, or the user is not active |
| 409 | Session data cannot produce valid statistics |
| 503 | Token verification is not configured or the database is unavailable |

---

## Endpoint index

| Method | Path | Auth | Source |
|---|---|---|---|
| GET | /health | No | main |
| POST | /auth/register | No | feature/6-auth |
| POST | /auth/login | No | feature/6-auth |
| GET | /auth/me | Bearer | feature/6-auth |
| PATCH | /auth/me | Bearer | feature/6-auth |
| GET | /datasets | Bearer | feature/replay-engine |
| POST | /sessions | Bearer | feature/replay-engine |
| GET | /sessions/{id} | Bearer | feature/replay-engine |
| GET | /sessions/{id}/bars | Bearer | feature/replay-engine |
| POST | /sessions/{id}/step | Bearer | feature/replay-engine |
| PATCH | /sessions/{id} | Bearer | feature/replay-engine |
| GET | /trades/{id}/outcome | Bearer | feature/replay-engine |
| POST | /sessions/{session_id}/stats/recompute | Bearer | feature/12-stats |
| GET | /sessions/{session_id}/stats | Bearer | feature/12-stats |
| GET | /stats/summary | Bearer | feature/12-stats |
