# Contributing to Epoch

This document describes how our team works in this repository.

## Workflow Summary

1. `main` is protected. Nobody pushes directly to it, including admins.
2. All work happens on a feature branch.
3. Changes reach `main` only through a pull request.
4. Every pull request needs **1 approving review** from a teammate before it can be merged.
5. If new commits are pushed after approval, the approval is dismissed and the PR needs to be reviewed again.

## Step by Step

### 1. Start from an up to date main

```bash
git checkout main
git pull origin main
```

### 2. Create a branch

Use one of these prefixes:

| Prefix      | Use for                              | Example                     |
| ----------- | ------------------------------------ | --------------------------- |
| `feature/`  | New functionality                    | `feature/replay-endpoint`   |
| `fix/`      | Bug fixes                            | `fix/trade-rounding`        |
| `docs/`     | Documentation only                   | `docs/api-overview`         |
| `chore/`    | Tooling, config, dependencies        | `chore/update-deps`         |

```bash
git checkout -b feature/short-description
```

### 3. Commit in small steps

Each commit should be a single change. Use this message format:

```
type: short description
```

Allowed types:

- `feat`: a new feature or capability
- `fix`: a bug fix
- `chore`: tooling, config, dependencies, or other maintenance
- `docs`: documentation only

Examples:

```
feat: add practice_sessions and trades tables from ERD
fix: reject trades with zero quantity
chore: add backend Dockerfile
docs: document replay endpoint
```

Keep the description short, lowercase, and in the present tense.

### 4. Push and open a pull request

```bash
git push -u origin feature/short-description
gh pr create --base main
```

In the PR description, include:

- What the change does
- How to test it
- Any related issue or task

### 5. Review

- Request a review from at least one teammate.
- Reviewers should check that the code runs, follows our design rules (see the README), and does not break existing features.
- Address feedback with new commits on the same branch.

### 6. Merge

Once the PR has 1 approval and no unresolved comments, the author merges it into `main` and deletes the branch.

## Design Rules to Check in Review

- Replay endpoints never return price bars past the session's current replay position.
- Cash and position updates for a trade happen in a single database transaction.
- Feedback text is generated only from verified, computed stats.
- No code connects to a real brokerage.
