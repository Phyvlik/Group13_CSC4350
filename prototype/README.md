# Epoch page prototype

Plain HTML, CSS and JavaScript version of the Epoch pages (sign in, dashboard, replay, statistics, journal, feedback, profile, admin). It is a design reference for the React pages in `frontend/`.

Replay, trading, stats and feedback logic is not here. The pages call `api` from `mock-api.js`, which returns fixed placeholder data. Replace each function there with a real request when the endpoint exists.

## Run

```bash
cd prototype
python -m http.server 5173
```

Open http://localhost:5173 and sign in with `demo@epoch.test` / `demo-demo` (trader) or `admin@epoch.test` / `admin-demo` (admin). These logins are placeholders stored in the browser.
