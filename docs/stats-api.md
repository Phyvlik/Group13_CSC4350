# Statistics API proposal — issue #12

This implements FR-12/FR-13 statistics and the verified-statistics portion of
NFR-9. It uses the team's `practice_sessions`, `trades`, `price_bars`,
`market_datasets`, `instruments`, `users`, `metrics`, and `session_metrics`
contracts. These routes do not create tables or run migrations.

**Integration remains pending:** the team schema must be merged and migrated,
the shared authentication service must issue compatible access tokens, and
trade/replay writers must participate in the session row-lock protocol. The
exposure formula and metric definitions below are proposed for team review.
Local SQLite contract tests do not establish PostgreSQL concurrency behavior
or a working deployed application. Coordinate these endpoints with the team's
planned `docs/api.md` before frontend integration.

## Authentication and ownership

Every route requires `Authorization: Bearer <access-token>`. Tokens must use
HS256, have an unexpired `exp`, and have a UUID user ID in `sub`. The user must
exist with `account_status = ACTIVE`. Configure `JWT_ALGORITHM=HS256` and a
random `JWT_SECRET_KEY` of at least 32 bytes; the template secret is rejected.
Do not commit the secret. This feature verifies tokens but does not provide
registration, login, password handling, or token issuance.

The authenticated token supplies the user ID. There is no user selector or
`X-User-Id` development bypass. Requests for another user's session have the
same 404 response as a nonexistent session. The isolated `stats_auth.py`
dependency should be consolidated with the shared auth service when it lands.

## Saved session statistics

### `POST /sessions/{session_id}/stats/recompute`

No request body. Calculate statistics from the owned session, save one new
revision, read back and compare the stored values, mark the revision verified,
and commit before returning 200. The session row is locked through the
transaction; trade and replay updates must acquire the same row lock to avoid
changing inputs during computation. Integrity and computation conflicts return 409 and roll back the request.
Operational database failures return 503; clients must not assume the write succeeded.

Metric definitions are versioned and seeded idempotently without overwriting
existing rules. An incompatible definition requires a new calculation version.
All observations in a revision share a computation and verification time.
Undefined metrics are omitted from storage and represented as `null` in JSON;
the reader does not substitute a value from an older revision.

### `GET /sessions/{session_id}/stats`

Return the latest saved, verified revision with 200. This is a **historical
snapshot as of `computed_at`**, not a claim that the latest trade/replay state
is unchanged. Explicitly recompute after trading or advancing replay when a
fresh saved snapshot is needed. GET does not save or recompute metrics. If no
verified revision exists, return 409.

Both routes return this shape; the UUID and values below are examples:

```json
{
  "session_id": "6792648b-cfd4-4d8a-a414-77f9b580eb37",
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

Monetary values and ratios are decimal strings, not binary floating-point
numbers. Stored values use the schema's `Numeric(18,6)` range, rounded to six
decimal places with `ROUND_HALF_EVEN`; overflow is rejected. Ratios range from
0 to 1. `win_rate` and `exposure_ratio` may be null. Timestamps are UTC.

## Current overall statistics

### `GET /stats/summary`

Calculate current totals from only the authenticated user's sessions and
revealed trades. This does not read, combine, or write historical metric
revisions. Results are grouped by quote currency; currencies are never added
together and no exchange-rate conversion is assumed. A user without sessions
receives `{"currencies": []}` with 200.

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

The aggregate win rate is total winning SELL fills divided by total SELL
fills, rather than an average of session percentages. Aggregate exposure is
total position value divided by total equity within the currency. If any
open position lacks a visible price, that currency's `position_value`,
`equity`, and `exposure_ratio` are all null. A zero equity denominator also
produces a null ratio. Current calculations use 38-digit Decimal precision;
their strings are not restricted to the six-decimal storage scale.

## Proposed calculation rules

- **P/L:** sum each SELL's recorded realized P/L, subtract every BUY/SELL fee
  once. Excludes unrealized P/L. BUY realized P/L must be null or zero.
- **Win rate:** each SELL fill, including a partial sell, counts as closed.
  Positive realized P/L before fees counts as a win; break-even does not.
  No SELL fills means null, not a measured zero percent.
- **Exposure:** for long-only, unleveraged practice accounts, position value
  is quantity multiplied by the latest visible closing price. Equity is cash
  plus position value; exposure is position value divided by equity. It is an
  invested-equity ratio, not a forecast of loss. Negative cash/quantity and
  nonpositive prices are rejected. A flat position does not require a price.

Price selection is bounded by the session's historical range and replay
position. Trade inputs are bounded by the same range and revealed replay position. No future
price values are returned by these endpoints.

## Error contract and local checks

| Status | Meaning |
| --- | --- |
| 401 | Missing/invalid token, or absent/inactive user |
| 404 | Session absent or owned by another user |
| 409 | No verified snapshot, invalid source data, or computation/storage conflict |
| 422 | Invalid UUID path parameter |
| 503 | Unsafe token-verification settings or unavailable/unmigrated database |

Errors expose short messages, not tokens, SQL statements, or driver details.
There is no automatic retry for a failed POST: the caller can explicitly retry
after resolving a conflict.

From `backend/`, install `requirements-dev.txt`, then run:

```sh
python -m unittest discover -s tests -v
```

The suite covers formulas, ownership, future-price boundaries, stored revisions,
JSON decimal/null contracts, rejected tokens, inactive accounts, and rollback
responses. HTTP tests use FastAPI TestClient and an independent SQLite schema;
separate PostgreSQL integration and concurrent trade/recompute testing remain
necessary before deployment.
