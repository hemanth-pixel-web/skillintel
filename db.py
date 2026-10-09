import os
import sqlite3
from pathlib import Path
from werkzeug.security import generate_password_hash

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = Path(os.getenv("DATABASE_PATH", BASE_DIR / "skillintel.db"))

def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def init_db():
    conn = get_conn()
    cur = conn.cursor()

    cur.executescript("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        role TEXT NOT NULL DEFAULT 'LEARNER',
        department TEXT DEFAULT 'Official Statistics',
        designation TEXT DEFAULT 'Statistical Officer',
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS sessions (
        token TEXT PRIMARY KEY,
        user_id INTEGER NOT NULL,
        expires_at TEXT NOT NULL,
        FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS skills (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE NOT NULL,
        category TEXT NOT NULL,
        description TEXT DEFAULT ''
    );

    CREATE TABLE IF NOT EXISTS user_skills (
        user_id INTEGER NOT NULL,
        skill_id INTEGER NOT NULL,
        score REAL NOT NULL DEFAULT 0,
        target REAL NOT NULL DEFAULT 80,
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY(user_id, skill_id),
        FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
        FOREIGN KEY(skill_id) REFERENCES skills(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS courses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL UNIQUE,
        provider TEXT NOT NULL,
        skill TEXT NOT NULL,
        level TEXT NOT NULL,
        duration TEXT NOT NULL,
        description TEXT NOT NULL,
        url TEXT DEFAULT '',
        source TEXT DEFAULT 'SKILLINTEL'
    );

    CREATE TABLE IF NOT EXISTS progress (
        user_id INTEGER NOT NULL,
        course_id INTEGER NOT NULL,
        percent INTEGER NOT NULL DEFAULT 0,
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY(user_id, course_id),
        FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
        FOREIGN KEY(course_id) REFERENCES courses(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS assessments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        score REAL NOT NULL,
        total INTEGER NOT NULL,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS assessment_answers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        assessment_id INTEGER NOT NULL,
        skill_id INTEGER NOT NULL,
        answer INTEGER NOT NULL,
        correct INTEGER NOT NULL,
        FOREIGN KEY(assessment_id) REFERENCES assessments(id) ON DELETE CASCADE,
        FOREIGN KEY(skill_id) REFERENCES skills(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS materials (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        filename TEXT NOT NULL,
        content TEXT NOT NULL,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS quizzes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        material_id INTEGER,
        title TEXT NOT NULL,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
        FOREIGN KEY(material_id) REFERENCES materials(id) ON DELETE SET NULL
    );

    CREATE TABLE IF NOT EXISTS quiz_questions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        quiz_id INTEGER NOT NULL,
        question TEXT NOT NULL,
        option_a TEXT NOT NULL,
        option_b TEXT NOT NULL,
        option_c TEXT NOT NULL,
        option_d TEXT NOT NULL,
        answer TEXT NOT NULL,
        explanation TEXT DEFAULT '',
        skill TEXT DEFAULT 'General',
        FOREIGN KEY(quiz_id) REFERENCES quizzes(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS quiz_attempts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        quiz_id INTEGER NOT NULL,
        user_id INTEGER NOT NULL,
        score INTEGER NOT NULL,
        total INTEGER NOT NULL,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(quiz_id) REFERENCES quizzes(id) ON DELETE CASCADE,
        FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS certificates (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        course_id INTEGER NOT NULL,
        certificate_code TEXT UNIQUE NOT NULL,
        issued_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
        FOREIGN KEY(course_id) REFERENCES courses(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS skill_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        skill_id INTEGER NOT NULL,
        score REAL NOT NULL,
        source TEXT DEFAULT 'assessment',
        recorded_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
        FOREIGN KEY(skill_id) REFERENCES skills(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS quiz_answers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        attempt_id INTEGER NOT NULL,
        question_id INTEGER NOT NULL,
        selected TEXT NOT NULL,
        correct INTEGER NOT NULL,
        FOREIGN KEY(attempt_id) REFERENCES quiz_attempts(id) ON DELETE CASCADE,
        FOREIGN KEY(question_id) REFERENCES quiz_questions(id) ON DELETE CASCADE
    );
    """)

    skills = [
        ("Data Collection & Survey Design", "Statistical Operations", "Designing sound data collection and survey instruments."),
        ("Statistical Analysis", "Statistical Methods", "Applying descriptive and inferential statistical methods."),
        ("Data Visualization", "Data Communication", "Communicating statistical insights through charts and dashboards."),
        ("Data Quality", "Statistical Operations", "Validation, consistency checks and quality assurance."),
        ("Python for Statistics", "Digital Skills", "Using Python for data processing and statistical workflows."),
        ("SQL & Data Management", "Digital Skills", "Querying, joining and managing structured datasets."),
        ("Official Statistics", "Domain Knowledge", "Understanding the production and dissemination of official statistics."),
        ("AI & Responsible Use", "Emerging Skills", "Using AI responsibly for productivity and learning."),
        ("Career & Employability Skills", "Professional Skills", "Resume building, interviews and workplace communication for students."),
        ("Office Productivity Tools", "Digital Skills", "Excel, presentations and everyday office software skills.")
    ]
    for name, category, desc in skills:
        cur.execute("INSERT OR IGNORE INTO skills(name, category, description) VALUES(?,?,?)",
                    (name, category, desc))

    courses = [
        ("Foundations of Official Statistics", "iGOT Karmayogi", "Official Statistics", "Beginner", "4h 20m",
         "Core concepts, statistical standards, dissemination and official statistical systems.",
         "https://igotkarmayogi.gov.in/", "iGOT"),
        ("Survey Design & Sampling Essentials", "iGOT Karmayogi", "Data Collection & Survey Design", "Intermediate", "5h 10m",
         "Sampling frames, questionnaires, non-response and survey quality.",
         "https://igotkarmayogi.gov.in/", "iGOT"),
        ("Practical Statistical Analysis", "SKILLINTEL Academy", "Statistical Analysis", "Intermediate", "6h 40m",
         "Descriptive statistics, correlation, regression and interpretation.",
         "#", "SKILLINTEL"),
        ("Data Visualization for Decision Makers", "SKILLINTEL Academy", "Data Visualization", "Beginner", "3h 45m",
         "Build clear charts and communicate evidence effectively.",
         "#", "SKILLINTEL"),
        ("Statistical Data Quality Management", "iGOT Karmayogi", "Data Quality", "Intermediate", "4h 55m",
         "Quality dimensions, validation rules, revisions and metadata.",
         "https://igotkarmayogi.gov.in/", "iGOT"),
        ("Python for Statistical Officers", "SKILLINTEL Academy", "Python for Statistics", "Intermediate", "7h 30m",
         "Python fundamentals, pandas and practical statistical workflows.",
         "#", "SKILLINTEL"),
        ("SQL for Official Data Systems", "SKILLINTEL Academy", "SQL & Data Management", "Intermediate", "5h 25m",
         "Queries, joins, aggregation, data validation and reporting.",
         "#", "SKILLINTEL"),
        ("Responsible AI in Government", "iGOT Karmayogi", "AI & Responsible Use", "Beginner", "2h 50m",
         "Responsible, transparent and secure use of AI in public-sector work.",
         "https://igotkarmayogi.gov.in/", "iGOT"),

        ("National Statistical System Orientation", "iGOT Karmayogi", "Official Statistics", "Beginner", "3h 00m",
         "Foundational course on India's Official Statistical System and MoSPI structure.",
         "https://igotkarmayogi.gov.in/", "iGOT"),
        ("Ethics in Public Service", "iGOT Karmayogi", "Official Statistics", "Beginner", "2h 15m",
         "Core Karmayogi Bharat module on integrity and conduct for government officers.",
         "https://igotkarmayogi.gov.in/", "iGOT"),
        ("Digital India Fundamentals", "iGOT Karmayogi", "AI & Responsible Use", "Beginner", "2h 40m",
         "Overview of Digital India initiatives relevant to statistical data collection.",
         "https://igotkarmayogi.gov.in/", "iGOT"),
        ("RTI & Data Transparency", "iGOT Karmayogi", "Data Quality", "Beginner", "1h 50m",
         "How the Right to Information Act intersects with official data release.",
         "https://igotkarmayogi.gov.in/", "iGOT"),
        ("Census Operations Essentials", "iGOT Karmayogi", "Data Collection & Survey Design", "Intermediate", "5h 00m",
         "Field methodology and enumeration standards used in national census work.",
         "https://igotkarmayogi.gov.in/", "iGOT"),

        ("Advanced Regression & Hypothesis Testing", "SKILLINTEL Academy", "Statistical Analysis", "Advanced", "8h 10m",
         "Deep dive into regression models, confidence intervals and significance testing.",
         "#", "SKILLINTEL"),
        ("Dashboards with Power BI for Statisticians", "SKILLINTEL Academy", "Data Visualization", "Intermediate", "4h 30m",
         "Build interactive government reporting dashboards.",
         "#", "SKILLINTEL"),
        ("Data Cleaning & Validation Workflows", "SKILLINTEL Academy", "Data Quality", "Beginner", "3h 20m",
         "Practical techniques to detect and correct data quality issues.",
         "#", "SKILLINTEL"),
        ("Advanced Pandas for Analysts", "SKILLINTEL Academy", "Python for Statistics", "Advanced", "6h 00m",
         "Advanced dataframe operations, performance tuning and pipelines.",
         "#", "SKILLINTEL"),
        ("Database Design for Statistical Systems", "SKILLINTEL Academy", "SQL & Data Management", "Advanced", "6h 15m",
         "Schema design, indexing and normalization for large statistical datasets.",
         "#", "SKILLINTEL"),
        ("Survey Questionnaire Design Workshop", "SKILLINTEL Academy", "Data Collection & Survey Design", "Beginner", "3h 00m",
         "Craft clear, unbiased questionnaires for field surveys.",
         "#", "SKILLINTEL"),
        ("AI Tools for Public Sector Productivity", "SKILLINTEL Academy", "AI & Responsible Use", "Intermediate", "3h 40m",
         "Practical, responsible use of AI tools in day-to-day statistical work.",
         "#", "SKILLINTEL"),

        ("Data Collection & Survey Design", "SKILLINTEL Academy", "Data Collection & Survey Design", "Beginner", "2h 45m",
         "Mobile data collection tools (CAPI/CATI) for field enumerators.",
         "#", "SKILLINTEL"),
        ("Non-Response & Weighting Adjustments", "SKILLINTEL Academy", "Data Collection & Survey Design", "Advanced", "4h 10m",
         "Handling survey non-response and calculating design weights.",
         "#", "SKILLINTEL"),
        ("Panel Survey Management", "iGOT Karmayogi", "Data Collection & Survey Design", "Intermediate", "3h 30m",
         "Managing longitudinal panel surveys and respondent tracking.",
         "https://igotkarmayogi.gov.in/", "iGOT"),

        ("Time Series Analysis for Economic Indicators", "SKILLINTEL Academy", "Statistical Analysis", "Advanced", "7h 00m",
         "Trend, seasonality and forecasting methods for economic data.",
         "#", "SKILLINTEL"),
        ("Introduction to Inferential Statistics", "iGOT Karmayogi", "Statistical Analysis", "Beginner", "3h 15m",
         "Confidence intervals, p-values and hypothesis testing basics.",
         "https://igotkarmayogi.gov.in/", "iGOT"),
        ("Index Numbers & Price Statistics", "SKILLINTEL Academy", "Statistical Analysis", "Intermediate", "4h 45m",
         "Construction and interpretation of CPI, WPI and other index numbers.",
         "#", "SKILLINTEL"),

        ("Infographics for Public Reports", "SKILLINTEL Academy", "Data Visualization", "Beginner", "2h 30m",
         "Designing clear infographics for non-technical audiences.",
         "#", "SKILLINTEL"),
        ("Geospatial Data Visualization", "iGOT Karmayogi", "Data Visualization", "Intermediate", "4h 00m",
         "Mapping statistical data using GIS-based visualization tools.",
         "https://igotkarmayogi.gov.in/", "iGOT"),
        ("Storytelling with Data", "SKILLINTEL Academy", "Data Visualization", "Intermediate", "3h 20m",
         "Structuring a narrative around data for policy audiences.",
         "#", "SKILLINTEL"),

        ("Metadata Standards for Statistical Data", "iGOT Karmayogi", "Data Quality", "Intermediate", "3h 10m",
         "SDMX and other metadata standards for official statistics.",
         "https://igotkarmayogi.gov.in/", "iGOT"),
        ("Data Auditing & Revision Policies", "SKILLINTEL Academy", "Data Quality", "Advanced", "4h 20m",
         "Establishing audit trails and revision policies for published data.",
         "#", "SKILLINTEL"),

        ("Python Basics for Absolute Beginners", "SKILLINTEL Academy", "Python for Statistics", "Beginner", "5h 00m",
         "Variables, loops, functions and basic scripting in Python.",
         "#", "SKILLINTEL"),
        ("Automating Reports with Python", "SKILLINTEL Academy", "Python for Statistics", "Intermediate", "4h 15m",
         "Scripting recurring statistical reports and data pipelines.",
         "#", "SKILLINTEL"),
        ("Data Wrangling with NumPy & Pandas", "iGOT Karmayogi", "Python for Statistics", "Intermediate", "5h 30m",
         "Cleaning, reshaping and merging datasets efficiently.",
         "https://igotkarmayogi.gov.in/", "iGOT"),

        ("SQL Fundamentals for Beginners", "SKILLINTEL Academy", "SQL & Data Management", "Beginner", "3h 45m",
         "SELECT, WHERE, JOIN and GROUP BY from the ground up.",
         "#", "SKILLINTEL"),
        ("Data Warehousing Concepts", "iGOT Karmayogi", "SQL & Data Management", "Advanced", "5h 45m",
         "Star schemas, ETL pipelines and warehouse design for government data.",
         "https://igotkarmayogi.gov.in/", "iGOT"),

        ("MoSPI Systems & Publications Overview", "iGOT Karmayogi", "Official Statistics", "Beginner", "2h 20m",
         "Understanding key MoSPI publications, NSSO and CSO outputs.",
         "https://igotkarmayogi.gov.in/", "iGOT"),
        ("International Statistical Standards", "SKILLINTEL Academy", "Official Statistics", "Intermediate", "3h 50m",
         "UN Fundamental Principles and cross-country comparability standards.",
         "#", "SKILLINTEL"),
        ("SDGs & National Indicator Frameworks", "iGOT Karmayogi", "Official Statistics", "Intermediate", "3h 05m",
         "Mapping Sustainable Development Goal indicators to national data.",
         "https://igotkarmayogi.gov.in/", "iGOT"),

        ("Machine Learning Foundations for Analysts", "SKILLINTEL Academy", "AI & Responsible Use", "Intermediate", "6h 20m",
         "Core ML concepts applied to statistical forecasting problems.",
         "#", "SKILLINTEL"),
        ("AI Ethics & Data Privacy in Government", "iGOT Karmayogi", "AI & Responsible Use", "Beginner", "2h 10m",
         "Privacy-preserving data practices and ethical AI deployment.",
         "https://igotkarmayogi.gov.in/", "iGOT"),
        ("Prompt Engineering for Public Servants", "SKILLINTEL Academy", "AI & Responsible Use", "Beginner", "1h 45m",
         "Writing effective prompts to use AI assistants productively at work.",
         "#", "SKILLINTEL"),

        ("Resume Writing & Personal Branding", "SKILLINTEL Academy", "Career & Employability Skills", "Beginner", "2h 00m",
         "Craft a strong resume and LinkedIn profile for job applications.",
         "#", "SKILLINTEL"),
        ("Interview Skills for Freshers", "SKILLINTEL Academy", "Career & Employability Skills", "Beginner", "2h 30m",
         "Common interview formats, STAR method and mock question practice.",
         "#", "SKILLINTEL"),
        ("Workplace Communication Essentials", "iGOT Karmayogi", "Career & Employability Skills", "Beginner", "2h 15m",
         "Professional email writing, meetings and workplace etiquette.",
         "https://igotkarmayogi.gov.in/", "iGOT"),
        ("Time Management & Productivity", "SKILLINTEL Academy", "Career & Employability Skills", "Beginner", "1h 50m",
         "Practical techniques to plan tasks and manage deadlines.",
         "#", "SKILLINTEL"),
        ("Public Speaking & Presentation Skills", "SKILLINTEL Academy", "Career & Employability Skills", "Intermediate", "3h 00m",
         "Structuring and delivering confident presentations.",
         "#", "SKILLINTEL"),
        ("Group Discussion & Teamwork Skills", "iGOT Karmayogi", "Career & Employability Skills", "Beginner", "1h 40m",
         "Participating effectively in group discussions and team settings.",
         "https://igotkarmayogi.gov.in/", "iGOT"),
        ("Government Job Exam Preparation Basics", "SKILLINTEL Academy", "Career & Employability Skills", "Beginner", "4h 00m",
         "Aptitude, reasoning and general awareness prep for competitive exams.",
         "#", "SKILLINTEL"),

        ("Microsoft Excel for Data Analysis", "SKILLINTEL Academy", "Office Productivity Tools", "Beginner", "4h 30m",
         "Formulas, pivot tables and charts for everyday data tasks.",
         "#", "SKILLINTEL"),
        ("Advanced Excel: Macros & VBA", "SKILLINTEL Academy", "Office Productivity Tools", "Advanced", "5h 15m",
         "Automating repetitive spreadsheet tasks with macros and VBA.",
         "#", "SKILLINTEL"),
        ("Professional Presentations with PowerPoint", "iGOT Karmayogi", "Office Productivity Tools", "Beginner", "2h 00m",
         "Designing clean, effective slide decks for official reporting.",
         "https://igotkarmayogi.gov.in/", "iGOT"),
        ("Document Drafting in MS Word", "SKILLINTEL Academy", "Office Productivity Tools", "Beginner", "1h 45m",
         "Formatting official letters, reports and templates efficiently.",
         "#", "SKILLINTEL"),
        ("Google Workspace for Collaboration", "SKILLINTEL Academy", "Office Productivity Tools", "Beginner", "2h 10m",
         "Docs, Sheets and Forms for collaborative government workflows.",
         "#", "SKILLINTEL"),
        ("Email & Digital Etiquette", "iGOT Karmayogi", "Office Productivity Tools", "Beginner", "1h 20m",
         "Writing clear, professional emails and managing digital correspondence.",
         "https://igotkarmayogi.gov.in/", "iGOT"),
        ("Cybersecurity Basics for Office Staff", "iGOT Karmayogi", "Office Productivity Tools", "Beginner", "2h 05m",
         "Recognizing phishing, password hygiene and safe data handling.",
         "https://igotkarmayogi.gov.in/", "iGOT"),
        ("Cloud Storage & File Management", "SKILLINTEL Academy", "Office Productivity Tools", "Beginner", "1h 30m",
         "Organizing, sharing and backing up files using cloud tools.",
         "#", "SKILLINTEL")
    ]
    for c in courses:
        cur.execute("""INSERT OR IGNORE INTO courses
        (title,provider,skill,level,duration,description,url,source)
        VALUES(?,?,?,?,?,?,?,?)""", c)

    cur.execute("SELECT id FROM users WHERE email=?", ("demo@skillintel.gov.in",))
    if not cur.fetchone():
        cur.execute("""INSERT INTO users(name,email,password_hash,role,department,designation)
                       VALUES(?,?,?,?,?,?)""",
                    ("Demo Learner", "demo@skillintel.gov.in",
                     generate_password_hash("Demo@123"), "LEARNER",
                     "National Statistical Office", "Statistical Officer"))

    cur.execute("SELECT id FROM users WHERE email=?", ("demo@skillintel.gov.in",))
    demo_id = cur.fetchone()["id"]
    skill_rows = cur.execute("SELECT id,name FROM skills ORDER BY id").fetchall()
    demo_scores = {
        "Data Collection & Survey Design": 72,
        "Statistical Analysis": 58,
        "Data Visualization": 76,
        "Data Quality": 64,
        "Python for Statistics": 45,
        "SQL & Data Management": 52,
        "Official Statistics": 82,
        "AI & Responsible Use": 68,
        "Career & Employability Skills": 60,
        "Office Productivity Tools": 74
    }
    for s in skill_rows:
        cur.execute("""INSERT OR IGNORE INTO user_skills(user_id,skill_id,score,target)
                       VALUES(?,?,?,80)""", (demo_id, s["id"], demo_scores.get(s["name"], 50)))

    # Seed a baseline + interim history for the demo learner so the
    # before/after graph and growth tracker have something to show.
    has_history = cur.execute("SELECT 1 FROM skill_history WHERE user_id=? LIMIT 1", (demo_id,)).fetchone()
    if not has_history:
        # Varied, realistic-looking growth per skill rather than a uniform jump.
        offsets = {
            "Data Collection & Survey Design": 24, "Statistical Analysis": 31,
            "Data Visualization": 18, "Data Quality": 27,
            "Python for Statistics": 33, "SQL & Data Management": 21,
            "Official Statistics": 14, "AI & Responsible Use": 29,
            "Career & Employability Skills": 20, "Office Productivity Tools": 16
        }
        for s in skill_rows:
            current = demo_scores.get(s["name"], 50)
            gain = offsets.get(s["name"], 22)
            baseline = max(8, current - gain)
            midpoint = max(baseline, current - round(gain * 0.55))
            cur.execute("""INSERT INTO skill_history(user_id,skill_id,score,source,recorded_at)
                           VALUES(?,?,?,?,datetime('now','-90 days'))""",
                        (demo_id, s["id"], baseline, "baseline"))
            cur.execute("""INSERT INTO skill_history(user_id,skill_id,score,source,recorded_at)
                           VALUES(?,?,?,?,datetime('now','-45 days'))""",
                        (demo_id, s["id"], midpoint, "assessment"))
            cur.execute("""INSERT INTO skill_history(user_id,skill_id,score,source,recorded_at)
                           VALUES(?,?,?,?,datetime('now','-1 days'))""",
                        (demo_id, s["id"], current, "assessment"))

    # Administrator account for the Admin Dashboard
    cur.execute("SELECT id FROM users WHERE email=?", ("admin@skillintel.gov.in",))
    if not cur.fetchone():
        cur.execute("""INSERT INTO users(name,email,password_hash,role,department,designation)
                       VALUES(?,?,?,?,?,?)""",
                    ("System Administrator", "admin@skillintel.gov.in",
                     generate_password_hash("Admin@123"), "ADMIN",
                     "National Statistical Office", "Platform Administrator"))

    conn.commit()
    conn.close()
