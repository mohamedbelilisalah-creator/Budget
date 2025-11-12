# Universal Budget Dashboard

A mobile-friendly Streamlit app for budgeting with goals, guardrails, no-spend tracking, and PDF reports.

## Files to upload to GitHub
- `app.py` (main app)
- `requirements.txt`
- `budget_starter_universal.csv` (optional sample data)
- `README.md` (this file)
- `Procfile` and `Dockerfile` (only needed for Render/Docker)

## Deploy on Streamlit Community Cloud (phone-friendly)
1. Create a new GitHub repo and upload these files.
2. Go to https://share.streamlit.io → New app.
3. Select your repo, set main file to `app.py`, Deploy.

## Local run (optional)
```bash
pip install -r requirements.txt
streamlit run app.py
```

## Data format
Required: `Category` | `Type` (Income/Expense) | `Budget (€)` | `Actual (€)`
Optional: `Month` (YYYY-MM) | `Date` (YYYY-MM-DD) | `Section` (Needs/Wants/Savings)
