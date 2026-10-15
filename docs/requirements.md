# Epoch Requirements

This document lists the functional (FR) and non-functional (NFR) requirements for Epoch, a trading practice and behavior analyzer. Feature work is tracked in GitHub issues that reference these IDs.

## Functional Requirements

### Market Replay

| ID   | Requirement |
| ---- | ----------- |
| FR-1 | Select a historical date range and instrument before starting a session. |
| FR-2 | Show historical prices while hiding all data past the current replay point. |
| FR-3 | Step the replay forward at a controllable pace. |
| FR-4 | Reveal the actual next price movement only after the user records a trade decision. |

### Paper Trading

| ID   | Requirement |
| ---- | ----------- |
| FR-5 | Give each user a virtual cash balance. |
| FR-6 | Place simulated buy and sell orders. |
| FR-7 | Recompute cash and position right after every trade. |
| FR-8 | Reject orders that exceed available cash or position. |

### Trade Journal

| ID    | Requirement |
| ----- | ----------- |
| FR-9  | Prompt the user to record reasoning before the outcome is revealed. |
| FR-10 | Store each journal entry with its trade, timestamp, and session. |
| FR-11 | Browse, search, and edit past journal entries. |

### Statistics

| ID    | Requirement |
| ----- | ----------- |
| FR-12 | Calculate P/L, win rate, and risk exposure per session. |
| FR-13 | Aggregate stats across all sessions. |

### Behavior Feedback

| ID    | Requirement |
| ----- | ----------- |
| FR-14 | Detect recurring behavior patterns like bigger positions after a loss. |
| FR-15 | Feedback cites the specific trades and stats behind each pattern. |
| FR-16 | Let the user track a chosen habit across sessions. |

### Accounts and Data

| ID    | Requirement |
| ----- | ----------- |
| FR-17 | Register and log in. |
| FR-18 | View and update profile. |
| FR-19 | Store users, sessions, trades, and journal entries in the database. |

### Administration

| ID    | Requirement |
| ----- | ----------- |
| FR-20 | Admin imports and manages historical market data. |
| FR-21 | Admin views and manages user accounts. |

## Non-Functional Requirements

| ID     | Category       | Requirement |
| ------ | -------------- | ----------- |
| NFR-7  | Integrity      | Replay never exposes future prices, even in API responses. |
| NFR-8  | Reliability    | Cash and position updates are atomic. |
| NFR-9  | Accuracy       | Feedback only uses computed and verified stats. |
| NFR-10 | Security       | Passwords hashed and salted. |
| NFR-12 | Security       | Every API request authenticated and scoped to the user. |

## Traceability

| Feature              | Requirements                     |
| -------------------- | -------------------------------- |
| Auth                 | FR-17, FR-18, NFR-10, NFR-12     |
| Market data import   | FR-20                            |
| Replay engine        | FR-1, FR-2, FR-3, FR-4, NFR-7    |
| Paper trading        | FR-5, FR-6, FR-7, FR-8, NFR-8    |
| Trade journal        | FR-9, FR-10, FR-11               |
| Stats                | FR-12, FR-13                     |
| Behavior feedback    | FR-14, FR-15, FR-16, NFR-9       |
| Database schema      | FR-19                            |
| Admin user management | FR-21                          |
