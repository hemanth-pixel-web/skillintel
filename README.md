# SKILLINTEL — AI-Powered Skill Intelligence & Learning Platform

**Tagline:** Know your skills. Discover your gaps. Build your future.

This project implements the supplied SIH-style problem statement for an AI-enabled learning platform serving India's Official Statistical System.

## What is included

- Secure learner registration/login
- Professional responsive dashboard
- Competency/skill assessment
- Automatic competency-gap analysis
- Personalized learning recommendations
- iGOT Karmayogi course catalogue adapter/demo
- Course progress tracking
- Upload learning material (`.txt`, `.md`, `.csv`, `.pdf`)
- AI-generated MCQs/quizzes from uploaded material
- Quiz scoring and performance analysis
- Skill profile updates after assessments/quizzes
- Built-in AI learning assistant
- SQLite database with no external database server required
- Optional PostgreSQL/LLM integration can be added later
- Single Flask server serves both frontend and backend

## Technology

Frontend:
- HTML5
- CSS3
- Vanilla JavaScript
- No frontend build step
- No npm required

Backend:
- Python 3.10+
- Flask
- SQLite
- Werkzeug password hashing
- Optional `pypdf` for PDF text extraction

## Run locally

### Windows
```bash
cd SKILLINTEL
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python backend/app.py
```

### Linux/macOS
```bash
cd SKILLINTEL
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python backend/app.py
```

Open:
`http://127.0.0.1:5000`

A demo learner is automatically created:

- Email: `demo@skillintel.gov.in`
- Password: `Demo@123`

You can also create a new account.

## Deployment

The application is a normal Flask web application. Any platform that supports Python/Flask can run it.

Production command:
```bash
gunicorn backend.app:app
```

The SQLite database is created automatically on first run. For a multi-instance production deployment, replace SQLite with PostgreSQL.

## Project structure

```text
SKILLINTEL/
├── frontend/
│   ├── index.html
│   ├── styles.css
│   └── app.js
├── backend/
│   ├── __init__.py
│   ├── app.py
│   ├── db.py
│   ├── auth.py
│   ├── ai_engine.py
│   └── services.py
├── database/
│   └── README.md
├── docs/
│   └── API.md
├── requirements.txt
├── .env.example
├── Procfile
└── Dockerfile
```

## AI architecture

The included AI engine is intentionally self-contained so the project works without an API key. It uses:

1. competency scoring from assessment responses;
2. skill-gap ranking;
3. rule-based course personalization;
4. document sentence extraction;
5. MCQ generation using concepts from the uploaded material;
6. performance feedback.

For a production SIH deployment, `backend/ai_engine.py` is the integration point for an LLM/RAG provider. The rest of the application does not need to change.

## iGOT integration

`backend/services.py` contains an iGOT adapter interface and a safe local catalogue fallback. Replace the adapter's `get_courses()` implementation with the official authenticated iGOT API once official credentials/endpoints are provided.

## Important

This is a complete working prototype/reference implementation. It does not claim to access private iGOT APIs without official credentials. The local adapter keeps the website fully demonstrable offline.
