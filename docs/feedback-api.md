# Feedback and habit tracking

Issue #13 · FR-14–16 · NFR-9. All routes use Bearer authentication and are scoped to the current user, including admins.

## Endpoints

| Method | Path | Behavior |
| --- | --- | --- |
| GET | `/sessions/{id}/feedback` | Read the latest saved analysis. Returns `status: not_computed` before the first analysis. |
| POST | `/sessions/{id}/feedback/recompute` | Compute and verify feedback. Reuses an unchanged verified result. Changed inputs create a revision. |
| GET | `/habits` | Return supported metrics and the user's active selection. |
| POST | `/habits` | Send `{ "metric_id": "uuid", "active": true }` to select a metric. Switching metrics deactivates the previous selection. Use `active: false` to stop tracking and retain history. |
| GET | `/habits/{metric_id}/history?limit=50&offset=0` | Latest verified values across sessions for the active metric, newest first. Returns `has_more`. Accepts limits of 1–100 and offsets of 0–100000. |

Feedback includes the analysis version, verified metric, explanation, supporting trade IDs, and saved journal context. History includes session ID, start time, currency, value, revision, and computation/verification times. Decimal values are strings; timestamps are UTC.

Recompute after trades or journal edits to refresh the saved snapshot. History skips undefined values and preserves the currency of each session. Statistics use the newest batch. LOSS_CHASING has a separate revision sequence. An unverified observation in the latest batch returns 409.

## Detection rule

`loss-chasing-v2` measures the number of unusually large positions following a loss.

- Reconstruct total holdings from every eligible BUY and SELL, starting at zero for each session. Negative holdings are invalid for this long-only model.
- Compare total holdings after a BUY with the mean of the last 20 earlier post-BUY holdings, requiring at least 3 samples from the same user and instrument.
- Prior sessions must be completed and have ended before the selected session started. Fills must be within their session's allowed range and replay position. Their holdings are reconstructed before selecting baseline samples.
- Count the first later BUY after a SELL with stored `realized_pnl < 0` when the resulting total holdings are at least 1.5× the baseline. An intervening BUY or non-losing SELL ends that opportunity.
- Timestamp ties update net holdings but cannot establish execution order. Exclude these groups from both baseline samples and causal pairing.
- Save the event count, including zero. Two or more events produce recurring feedback.
- Each explanation cites the qualifying trades, loss, buy quantity, holdings before and after the buy, baseline mean, and contributing trade IDs. It includes saved journal text on the loss or subsequent buy when available.

## Storage and errors

Run `alembic upgrade head` before starting the API. Migration `0002` seeds the version 2 LOSS_CHASING metric and adds `feedback_analyses` to preserve input fingerprints and evidence snapshots, including zero-event results.

Analysis locks the session, persists the observation, and verifies the stored value and reloaded inputs before creating feedback evidence. Verification failure rolls back the request. Habit selection locks the user and uses the existing composite key to avoid duplicate selections.

| HTTP status | Cause |
| --- | --- |
| 401 | Missing or invalid token |
| 404 | Unknown metric, missing session, another user's session, or history for an inactive metric |
| 409 | Conflicting inputs, unverifiable evidence, or an unverified observation |
| 422 | Invalid request fields or pagination |
| 503 | Feedback database unavailable |

## Tests and dependencies

Run `pytest -q` in `backend/`, and `npm test` plus `npm run build` in `frontend/`. PostgreSQL provides the row locks that serialize concurrent analyses and habit selections.

Journal entries come from the journal table when available. P/L history reads the existing statistics service's verified observations.
