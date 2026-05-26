# FAIR Assessment Tool — Quick Reference

## First time setup (new device)

```bash
# 1. Clone the repo
git clone https://github.com/YOUR_USERNAME/fair-assessment-tool.git
cd fair-assessment-tool

# 2. Create virtual environment
python -m venv venv

# 3. Activate it (Windows)
venv\Scripts\activate

# 4. Install dependencies
pip install -r requirements.txt
```

---

## Every time you work on the project

```bash
# 1. Activate the virtual environment (do this first, always)
venv\Scripts\activate
# You should see (venv) in the terminal

# 2. Start the backend API
uvicorn app.main:app --reload
# API runs at http://localhost:8000
# Docs at http://localhost:8000/docs

# 3. Open the frontend
# In VS Code: right click frontend/index.html → Open with Live Server
# Or open directly in browser: Ctrl+O → frontend/index.html
```

---

## Git — saving your work

```bash
# Save current state to GitHub
git add .
git commit -m "describe what you changed"
git push

# Pull latest changes (on another device)
git pull

# Check what files have changed
git status

# See commit history
git log --oneline
```

---

## If something breaks

```bash
# Restart the API server
# Press Ctrl+C to stop, then:
uvicorn app.main:app --reload

# Reset the database (WARNING: deletes all assessment history)
Remove-Item fair_assessment.db
uvicorn app.main:app --reload

# Reinstall all packages
pip install -r requirements.txt

# Update requirements file after installing new packages
pip freeze > requirements.txt
```

---

## API endpoints (quick reference)

| Method | URL | What it does |
|--------|-----|--------------|
| GET | /profiles | List all profiles |
| POST | /profiles | Create new profile |
| PUT | /profiles/{name} | Update a profile |
| DELETE | /profiles/{name} | Delete a profile |
| POST | /profiles/{name}/restore | Restore profile to default |
| GET | /assess/{doi} | Run assessment on a DOI |
| GET | /metadata/{doi} | Fetch raw metadata for a DOI |
| GET | /history | All assessment history |
| GET | /history/{doi} | History for a specific DOI |
| DELETE | /history/run/{id} | Delete one assessment run |

---

## Project structure

```
fair-assessment/
├── app/
│   ├── main.py              ← FastAPI routes
│   ├── db.py                ← Database models
│   ├── models/
│   │   └── metadata.py      ← Internal metadata schema
│   │   └── profile.py       ← Profile + report models
│   └── services/
│       ├── retriever.py     ← Fetches metadata from DOI/APIs
│       ├── normalizer.py    ← Converts API response to internal schema
│       ├── evaluator.py     ← Runs FAIR metric checks
│       ├── profile_service.py ← Profile CRUD
│       └── history_service.py ← Assessment history CRUD
├── profiles/                ← Default domain profiles (JSON)
├── frontend/                ← HTML/CSS/JS user interface
├── tests/                   ← Unit tests
├── requirements.txt         ← Python dependencies
└── .vscode/settings.json    ← VS Code settings (Live Server fix)
```

---

## Common issues

**`venv\Scripts\activate` gives permission error**
```bash
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

**`uvicorn` not recognized**
```bash
# Make sure venv is activated first (you should see (venv))
venv\Scripts\activate
```

**Page refreshes after running assessment**
- VS Code Live Server is reloading on database changes
- Fix: Ctrl+Shift+P → Open User Settings JSON → add:
```json
"liveServer.settings.ignoreFiles": ["**/*.db", "**/*.db-shm", "**/*.db-wal"]
```

**Database schema changed / migration error**
```bash
Remove-Item fair_assessment.db
uvicorn app.main:app --reload
```
