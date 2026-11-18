"""Immutable metric definition used by the detector and migration 0002."""

from decimal import Decimal
from uuid import UUID, uuid5

ANALYSIS_VERSION = "loss-chasing-v2"
LOSS_CHASING_ID = uuid5(UUID("d654ef62-5706-45f1-a027-412547122d32"), ANALYSIS_VERSION)
MIN_BASELINE = 3
BASELINE_WINDOW = 20
SIZE_MULTIPLIER = Decimal("1.5")
MIN_RECURRING_EVENTS = 2
RULE = (
    "Proposed loss-chasing-v2: after a losing SELL, compare total holdings after the first later "
    "BUY with 1.5 times the mean of the last 20 earlier post-BUY holdings (minimum 3). "
    "Holdings start at zero per session and include every eligible BUY and SELL. "
    "Baseline positions belong to this user and instrument: completed sessions ended before "
    "this session started, then earlier positions in this session. Timestamp ties update net "
    "holdings but are excluded from baseline samples and causal pairing. An intervening BUY "
    "or non-losing SELL ends the opportunity. A losing SELL has stored realized_pnl < 0. "
    "Two or more events produce recurring feedback. Journal text is saved context, not an "
    "inference about intent. The metric counts events, not diagnoses or investment advice."
)
LOSS_DEFINITION = {
    "metric_id": LOSS_CHASING_ID,
    "code": "LOSS_CHASING",
    "name": "Larger positions after losses",
    "unit": "events",
    "calculation_version": ANALYSIS_VERSION,
    "calculation_rule": RULE,
}
