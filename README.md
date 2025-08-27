# Intertek Geronimo — Marketing Dashboard (Sales Rep Edition)

This is a self-contained Streamlit CRM & Marketing Dashboard tailored for a Sales Representative operating in Ghana (scalable to West Africa).
It includes: clients, contacts, interactions, campaigns & leads, meetings & opportunities, tasks & reminders, targets, reporting, user management, and export/import utilities.

## What's included
- `app.py` — The full Streamlit application (drop-in, run with `streamlit run app.py`).
- `crm.db` — Pre-seeded SQLite database with sample sectors, companies, contacts, and seeded interactions/campaigns/tasks.
- `requirements.txt` — Python dependencies.
- `README.md` — This file.

## Quick start
1. Create a virtualenv and install requirements:
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # or .venv\Scripts\activate on Windows
   pip install -r requirements.txt
   ```
2. Run the app:
   ```bash
   streamlit run app.py
   ```
3. Default login credentials (seeded):
   - username: `admin`
   - password: `password123`

## Notes
- The app stores its SQLite DB in the same folder (`crm.db`). You can copy it and keep backups.
- Use the "Reset & Reseed Demo Data" option in Settings to restore seeded demo content.
- Designed for weekly presentations (Monday & Thursday) — use the date filters and the Export tools to prepare slides quickly.