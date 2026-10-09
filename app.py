import os
import io
import secrets
from pathlib import Path
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash

from db import init_db, get_conn
from auth import create_session, auth_required, bearer_user, logout
from services import dashboard, get_skills_for_user, get_recommendations, igot_courses
from ai_engine import generate_mcqs, analyze_gaps, infer_skill

BASE_DIR = Path(__file__).resolve().parent
FRONTEND_DIR = BASE_DIR

app = Flask(__name__, static_folder=None)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "skillintel-development-secret")
CORS(app)

init_db()

def json_user(user):
    return {k:user[k] for k in ["id","name","email","role","department","designation"]}

@app.get("/")
def index():
    return send_from_directory(FRONTEND_DIR, "index.html")

@app.get("/<path:path>")
def static_files(path):
    target = FRONTEND_DIR / path
    if target.exists() and target.is_file():
        return send_from_directory(FRONTEND_DIR, path)
    return send_from_directory(FRONTEND_DIR, "index.html")

@app.get("/api/health")
def health():
    return jsonify({"status":"ok","service":"SKILLINTEL","version":"1.0"})

@app.post("/api/auth/register")
def register():
    data = request.get_json(force=True)
    name = (data.get("name") or "").strip()
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""
    department = (data.get("department") or "Official Statistics").strip()
    designation = (data.get("designation") or "Statistical Officer").strip()
    role = (data.get("role") or "LEARNER").strip().upper()
    if role not in ("LEARNER","TRAINER"):
        role = "LEARNER"  # ADMIN accounts are not self-service; only LEARNER/TRAINER can self-register
    if len(name) < 2 or "@" not in email or len(password) < 6:
        return jsonify({"error":"Enter a valid name, email and password of at least 6 characters."}), 400

    conn = get_conn()
    try:
        cur = conn.execute("""INSERT INTO users(name,email,password_hash,role,department,designation)
                              VALUES(?,?,?,?,?,?)""",
                           (name,email,generate_password_hash(password),role,department,designation))
        uid = cur.lastrowid
        for s in conn.execute("SELECT id FROM skills").fetchall():
            conn.execute("INSERT INTO user_skills(user_id,skill_id,score,target) VALUES(?,?,50,80)",
                         (uid,s["id"]))
        conn.commit()
    except Exception:
        conn.rollback()
        conn.close()
        return jsonify({"error":"An account with that email already exists."}), 409
    conn.close()
    token = create_session(uid)
    return jsonify({"token":token,"user":json_user({"id":uid,"name":name,"email":email,
        "role":role,"department":department,"designation":designation})})

@app.post("/api/auth/login")
def login():
    data = request.get_json(force=True)
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""
    conn = get_conn()
    row = conn.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
    conn.close()
    if not row or not check_password_hash(row["password_hash"], password):
        return jsonify({"error":"Invalid email or password."}), 401
    token = create_session(row["id"])
    return jsonify({"token":token,"user":json_user(dict(row))})

@app.post("/api/auth/logout")
def logout_route():
    header = request.headers.get("Authorization","")
    token = header.replace("Bearer ","",1).strip() if header.startswith("Bearer ") else ""
    logout(token)
    return jsonify({"message":"Logged out"})

@app.get("/api/me")
@auth_required
def me(user):
    return jsonify({"user":json_user(user)})

@app.post("/api/auth/change-password")
@auth_required
def change_password(user):
    data = request.get_json(force=True)
    current = data.get("current_password") or ""
    new_pass = data.get("new_password") or ""
    if len(new_pass) < 6:
        return jsonify({"error":"New password must be at least 6 characters."}),400
    conn = get_conn()
    row = conn.execute("SELECT password_hash FROM users WHERE id=?", (user["id"],)).fetchone()
    if not row or not check_password_hash(row["password_hash"], current):
        conn.close()
        return jsonify({"error":"Current password is incorrect."}),401
    conn.execute("UPDATE users SET password_hash=? WHERE id=?",
                (generate_password_hash(new_pass), user["id"]))
    conn.commit()
    conn.close()
    return jsonify({"message":"Password updated successfully."})

@app.get("/api/dashboard")
@auth_required
def get_dashboard(user):
    return jsonify(dashboard(user["id"]))

@app.get("/api/skills")
@auth_required
def skills(user):
    return jsonify({"skills":get_skills_for_user(user["id"])})

@app.get("/api/recommendations")
@auth_required
def recommendations(user):
    return jsonify({"recommendations":get_recommendations(user["id"])})

@app.get("/api/courses")
@auth_required
def courses(user):
    conn = get_conn()
    rows = conn.execute("SELECT * FROM courses ORDER BY source DESC,id").fetchall()
    conn.close()
    return jsonify({"courses":[dict(r) for r in rows]})

@app.get("/api/igot/courses")
@auth_required
def get_igot_courses(user):
    return jsonify({"courses":igot_courses()})

@app.post("/api/progress")
@auth_required
def update_progress(user):
    data = request.get_json(force=True)
    course_id = int(data.get("course_id",0))
    percent = max(0,min(100,int(data.get("percent",0))))
    conn = get_conn()
    course = conn.execute("SELECT id,title FROM courses WHERE id=?", (course_id,)).fetchone()
    if not course:
        conn.close()
        return jsonify({"error":"Course not found"}), 404
    conn.execute("""INSERT INTO progress(user_id,course_id,percent) VALUES(?,?,?)
                    ON CONFLICT(user_id,course_id) DO UPDATE SET percent=excluded.percent,
                    updated_at=CURRENT_TIMESTAMP""",
                 (user["id"],course_id,percent))

    certificate = None
    if percent >= 100:
        existing = conn.execute("""SELECT certificate_code FROM certificates
                                   WHERE user_id=? AND course_id=?""",
                                (user["id"],course_id)).fetchone()
        if existing:
            certificate = existing["certificate_code"]
        else:
            code = f"SKI-{secrets.token_hex(4).upper()}-{course_id}"
            conn.execute("""INSERT INTO certificates(user_id,course_id,certificate_code)
                            VALUES(?,?,?)""", (user["id"],course_id,code))
            certificate = code
    conn.commit()
    conn.close()
    return jsonify({"message":"Progress updated","percent":percent,"certificate_code":certificate})

@app.get("/api/certificates")
@auth_required
def list_certificates(user):
    conn = get_conn()
    rows = conn.execute("""
        SELECT cert.certificate_code, cert.issued_at, c.title, c.skill, c.provider
        FROM certificates cert JOIN courses c ON c.id=cert.course_id
        WHERE cert.user_id=? ORDER BY cert.issued_at DESC""", (user["id"],)).fetchall()
    conn.close()
    return jsonify({"certificates":[dict(r) for r in rows]})

@app.get("/api/certificates/<code>")
@auth_required
def get_certificate(user,code):
    conn = get_conn()
    row = conn.execute("""
        SELECT cert.certificate_code, cert.issued_at, c.title, c.skill, c.provider, c.duration,
               u.name as learner_name
        FROM certificates cert
        JOIN courses c ON c.id=cert.course_id
        JOIN users u ON u.id=cert.user_id
        WHERE cert.certificate_code=? AND cert.user_id=?""", (code,user["id"])).fetchone()
    conn.close()
    if not row:
        return jsonify({"error":"Certificate not found"}), 404
    return jsonify({"certificate":dict(row)})


ASSESSMENT = [
    {"skill":"Data Collection & Survey Design","q":"Which sampling method gives every member of a population a known, non-zero probability of selection?","options":["Probability sampling","Convenience sampling","Snowball sampling","Voluntary response"],"answer":0},
    {"skill":"Statistical Analysis","q":"Which measure is least affected by an extreme outlier?","options":["Mean","Median","Variance","Range"],"answer":1},
    {"skill":"Data Visualization","q":"Which chart is generally suitable for comparing values across discrete categories?","options":["Bar chart","Scatter plot only","Histogram only","Box plot only"],"answer":0},
    {"skill":"Data Quality","q":"A validation rule that checks whether a value is within an allowed interval primarily addresses what?","options":["Range validity","Encryption","Sampling frame","Visualization"],"answer":0},
    {"skill":"Python for Statistics","q":"Which Python library is commonly used for tabular data manipulation?","options":["pandas","pygame","tkinter","turtle"],"answer":0},
    {"skill":"SQL & Data Management","q":"Which SQL clause filters rows before grouping?","options":["WHERE","HAVING","ORDER BY","GROUP"],"answer":0},
    {"skill":"Official Statistics","q":"Official statistics are primarily produced to provide what?","options":["Trusted evidence for society and policy","Entertainment content","Advertising slogans","Personal opinions"],"answer":0},
    {"skill":"AI & Responsible Use","q":"What is an important principle when using AI in public-sector decision support?","options":["Human oversight and accountability","Hide all model limitations","Use any personal data","Ignore bias"],"answer":0}
]

@app.get("/api/assessment/questions")
@auth_required
def assessment_questions(user):
    safe = [{k:v for k,v in q.items() if k!="answer"} for q in ASSESSMENT]
    return jsonify({"questions":safe})

@app.post("/api/assessment/submit")
@auth_required
def assessment_submit(user):
    data = request.get_json(force=True)
    answers = data.get("answers",[])
    if not isinstance(answers,list):
        return jsonify({"error":"Answers must be an array"}),400

    conn = get_conn()
    cur = conn.cursor()
    cur.execute("INSERT INTO assessments(user_id,score,total) VALUES(?,?,?)",
                (user["id"],0,len(ASSESSMENT)))
    assessment_id = cur.lastrowid
    correct_count = 0
    per_skill = {}
    for i,q in enumerate(ASSESSMENT):
        ans = answers[i] if i < len(answers) else -1
        try: ans = int(ans)
        except: ans = -1
        correct = int(ans == q["answer"])
        correct_count += correct
        per_skill.setdefault(q["skill"], [0,0])
        per_skill[q["skill"]][1] += 1
        per_skill[q["skill"]][0] += correct
        sid = conn.execute("SELECT id FROM skills WHERE name=?", (q["skill"],)).fetchone()["id"]
        conn.execute("""INSERT INTO assessment_answers(assessment_id,skill_id,answer,correct)
                        VALUES(?,?,?,?)""", (assessment_id,sid,ans,correct))

    score = correct_count * 100.0 / len(ASSESSMENT)
    conn.execute("UPDATE assessments SET score=? WHERE id=?", (score,assessment_id))
    for skill, (correct,total) in per_skill.items():
        sid = conn.execute("SELECT id FROM skills WHERE name=?", (skill,)).fetchone()["id"]
        new_score = correct/total*100
        conn.execute("""INSERT INTO user_skills(user_id,skill_id,score,target)
                        VALUES(?,?,?,80)
                        ON CONFLICT(user_id,skill_id) DO UPDATE SET score=excluded.score,
                        updated_at=CURRENT_TIMESTAMP""", (user["id"],sid,new_score))
        conn.execute("""INSERT INTO skill_history(user_id,skill_id,score,source)
                        VALUES(?,?,?,'assessment')""", (user["id"],sid,new_score))
    conn.commit()
    conn.close()
    gaps = analyze_gaps(get_skills_for_user(user["id"]))
    return jsonify({"score":round(score,1),"correct":correct_count,"total":len(ASSESSMENT),
                    "gaps":gaps,"message":"Assessment evaluated and your skill profile was updated."})

@app.get("/api/skills/history")
@auth_required
def skills_history(user):
    """Before/after comparison plus the full growth timeline per skill."""
    conn = get_conn()
    skills = conn.execute("SELECT id,name FROM skills ORDER BY id").fetchall()
    out = []
    timeline_dates = set()
    for s in skills:
        rows = conn.execute("""SELECT score,source,recorded_at FROM skill_history
                               WHERE user_id=? AND skill_id=? ORDER BY recorded_at""",
                            (user["id"], s["id"])).fetchall()
        current_row = conn.execute("""SELECT score FROM user_skills
                                      WHERE user_id=? AND skill_id=?""",
                                   (user["id"], s["id"])).fetchone()
        current = current_row["score"] if current_row else 0
        points = [{"score": round(r["score"],1), "source": r["source"],
                   "date": (r["recorded_at"] or "")[:10]} for r in rows]
        for p in points:
            if p["date"]:
                timeline_dates.add(p["date"])
        baseline = points[0]["score"] if points else current
        out.append({
            "skill": s["name"],
            "baseline": round(baseline,1),
            "current": round(current,1),
            "change": round(current - baseline,1),
            "points": points
        })
    conn.close()
    improved = [x for x in out if x["change"] > 0]
    total_change = round(sum(x["change"] for x in out)/len(out),1) if out else 0
    return jsonify({
        "skills": out,
        "dates": sorted(timeline_dates),
        "summary": {
            "skills_improved": len(improved),
            "total_skills": len(out),
            "average_growth": total_change,
            "most_improved": max(out, key=lambda x: x["change"])["skill"] if out else None
        }
    })

@app.get("/api/admin/stats")
@auth_required
def admin_stats(user):
    if (user.get("role") or "").upper() != "ADMIN":
        return jsonify({"error":"Administrator access required."}),403
    conn = get_conn()

    total_learners = conn.execute(
        "SELECT COUNT(*) c FROM users WHERE role!='ADMIN'").fetchone()["c"]
    active_learners = conn.execute("""
        SELECT COUNT(DISTINCT user_id) c FROM (
            SELECT user_id FROM progress
            UNION SELECT user_id FROM quiz_attempts
            UNION SELECT user_id FROM assessments
        )""").fetchone()["c"]
    total_courses = conn.execute("SELECT COUNT(*) c FROM courses").fetchone()["c"]
    total_quizzes = conn.execute("SELECT COUNT(*) c FROM quizzes").fetchone()["c"]
    total_attempts = conn.execute("SELECT COUNT(*) c FROM quiz_attempts").fetchone()["c"]

    # Competency distribution across all learners
    buckets = {"0-40":0, "41-60":0, "61-80":0, "81-100":0}
    rows = conn.execute("""SELECT AVG(score) avg_score FROM user_skills
                           GROUP BY user_id""").fetchall()
    for r in rows:
        v = r["avg_score"] or 0
        if v <= 40: buckets["0-40"] += 1
        elif v <= 60: buckets["41-60"] += 1
        elif v <= 80: buckets["61-80"] += 1
        else: buckets["81-100"] += 1

    # Course completion by course
    completion = conn.execute("""
        SELECT c.title, c.skill,
               COUNT(p.user_id) enrolled,
               SUM(CASE WHEN p.percent>=100 THEN 1 ELSE 0 END) completed
        FROM courses c LEFT JOIN progress p ON p.course_id=c.id
        GROUP BY c.id HAVING enrolled > 0
        ORDER BY enrolled DESC LIMIT 8""").fetchall()

    # Learner progress: average skill score per skill across all learners
    per_skill = conn.execute("""
        SELECT s.name, ROUND(AVG(us.score),1) avg_score, COUNT(us.user_id) learners
        FROM skills s LEFT JOIN user_skills us ON us.skill_id=s.id
        GROUP BY s.id ORDER BY s.id""").fetchall()

    # AI quiz usage over the last 7 days
    quiz_usage = conn.execute("""
        SELECT DATE(created_at) d, COUNT(*) c FROM quiz_attempts
        WHERE created_at >= datetime('now','-7 days')
        GROUP BY DATE(created_at) ORDER BY d""").fetchall()

    recent_learners = conn.execute("""
        SELECT name,email,department,designation,created_at FROM users
        WHERE role!='ADMIN' ORDER BY id DESC LIMIT 8""").fetchall()

    conn.close()
    return jsonify({
        "totals": {
            "learners": total_learners,
            "active_learners": active_learners,
            "courses": total_courses,
            "quizzes": total_quizzes,
            "quiz_attempts": total_attempts
        },
        "competency_distribution": buckets,
        "course_completion": [dict(r) for r in completion],
        "learner_progress": [dict(r) for r in per_skill],
        "quiz_usage": [dict(r) for r in quiz_usage],
        "recent_learners": [dict(r) for r in recent_learners]
    })

def extract_upload(file):
    name = file.filename.lower()
    raw = file.read()
    if name.endswith(".pdf"):
        try:
            from pypdf import PdfReader
            reader = PdfReader(io.BytesIO(raw))
            return "\n".join((p.extract_text() or "") for p in reader.pages)
        except Exception as exc:
            raise ValueError("PDF extraction failed. Try a text/Markdown file or install pypdf.")
    try:
        return raw.decode("utf-8", errors="ignore")
    except Exception:
        raise ValueError("The uploaded file could not be decoded as text.")

@app.post("/api/materials")
@auth_required
def upload_material(user):
    if "file" not in request.files:
        return jsonify({"error":"Choose a learning material file."}),400
    file = request.files["file"]
    if not file.filename:
        return jsonify({"error":"Choose a file."}),400
    allowed = (".txt",".md",".csv",".pdf")
    if not file.filename.lower().endswith(allowed):
        return jsonify({"error":"Supported formats: TXT, MD, CSV, PDF."}),400
    try:
        content = extract_upload(file)
    except ValueError as e:
        return jsonify({"error":str(e)}),400
    content = content.strip()
    if len(content) < 80:
        return jsonify({"error":"The material contains too little readable text to generate a useful quiz."}),400
    content = content[:50000]
    conn = get_conn()
    cur = conn.execute("INSERT INTO materials(user_id,filename,content) VALUES(?,?,?)",
                       (user["id"],file.filename,content))
    material_id = cur.lastrowid
    conn.commit()
    conn.close()
    return jsonify({"material_id":material_id,"filename":file.filename,
                    "characters":len(content),"skill":infer_skill(content),
                    "message":"Learning material uploaded successfully."})

@app.post("/api/quiz/generate")
@auth_required
def generate_quiz(user):
    data = request.get_json(force=True)
    material_id = data.get("material_id")
    count = max(3,min(10,int(data.get("count",5))))
    conn = get_conn()
    row = conn.execute("SELECT * FROM materials WHERE id=? AND user_id=?",
                       (material_id,user["id"])).fetchone()
    if not row:
        conn.close()
        return jsonify({"error":"Material not found"}),404
    questions = generate_mcqs(row["content"],count)
    if len(questions) < 3:
        conn.close()
        return jsonify({"error":"Not enough structured content to generate at least 3 questions."}),400
    title = f"AI Quiz — {row['filename']}"
    cur = conn.execute("INSERT INTO quizzes(user_id,material_id,title) VALUES(?,?,?)",
                       (user["id"],material_id,title))
    quiz_id = cur.lastrowid
    for q in questions:
        conn.execute("""INSERT INTO quiz_questions
        (quiz_id,question,option_a,option_b,option_c,option_d,answer,explanation,skill)
        VALUES(?,?,?,?,?,?,?,?,?)""",
        (quiz_id,q["question"],q["options"]["A"],q["options"]["B"],q["options"]["C"],
         q["options"]["D"],q["answer"],q["explanation"],q["skill"]))
    conn.commit()
    conn.close()
    return jsonify({"quiz_id":quiz_id,"title":title,"question_count":len(questions)})

@app.post("/api/quiz/generate-from-text")
@auth_required
def generate_quiz_from_text(user):
    data = request.get_json(force=True)
    text = (data.get("text") or "").strip()
    title = (data.get("title") or "AI Quiz").strip()
    count = max(3,min(10,int(data.get("count",5))))
    if len(text) < 30:
        return jsonify({"error":"Not enough text supplied to generate a quiz."}),400
    conn = get_conn()
    cur = conn.execute("INSERT INTO materials(user_id,filename,content) VALUES(?,?,?)",
                       (user["id"], title, text))
    material_id = cur.lastrowid
    questions = generate_mcqs(text,count)
    if len(questions) < 3:
        conn.close()
        return jsonify({"error":"Not enough structured content to generate at least 3 questions. Try a different course."}),400
    cur2 = conn.execute("INSERT INTO quizzes(user_id,material_id,title) VALUES(?,?,?)",
                       (user["id"],material_id,title))
    quiz_id = cur2.lastrowid
    for q in questions:
        conn.execute("""INSERT INTO quiz_questions
        (quiz_id,question,option_a,option_b,option_c,option_d,answer,explanation,skill)
        VALUES(?,?,?,?,?,?,?,?,?)""",
        (quiz_id,q["question"],q["options"]["A"],q["options"]["B"],q["options"]["C"],
         q["options"]["D"],q["answer"],q["explanation"],q["skill"]))
    conn.commit()
    conn.close()
    return jsonify({"quiz_id":quiz_id,"title":title,"question_count":len(questions)})

@app.get("/api/quizzes")
@auth_required
def quizzes(user):
    conn = get_conn()
    rows = conn.execute("""
        SELECT q.id,q.title,q.created_at,m.filename
        FROM quizzes q LEFT JOIN materials m ON m.id=q.material_id
        WHERE q.user_id=? ORDER BY q.id DESC
    """,(user["id"],)).fetchall()
    conn.close()
    return jsonify({"quizzes":[dict(r) for r in rows]})

@app.get("/api/quizzes/<int:quiz_id>")
@auth_required
def get_quiz(user,quiz_id):
    conn = get_conn()
    q = conn.execute("SELECT id,title FROM quizzes WHERE id=? AND user_id=?",(quiz_id,user["id"])).fetchone()
    if not q:
        conn.close()
        return jsonify({"error":"Quiz not found"}),404
    rows = conn.execute("""SELECT id,question,option_a,option_b,option_c,option_d,skill
                           FROM quiz_questions WHERE quiz_id=? ORDER BY id""",(quiz_id,)).fetchall()
    conn.close()
    return jsonify({"quiz":dict(q),"questions":[dict(r) for r in rows]})

@app.post("/api/quizzes/<int:quiz_id>/submit")
@auth_required
def submit_quiz(user,quiz_id):
    data = request.get_json(force=True)
    answers = data.get("answers",{})
    conn = get_conn()
    quiz = conn.execute("SELECT id FROM quizzes WHERE id=? AND user_id=?",(quiz_id,user["id"])).fetchone()
    if not quiz:
        conn.close()
        return jsonify({"error":"Quiz not found"}),404
    qs = conn.execute("SELECT * FROM quiz_questions WHERE quiz_id=? ORDER BY id",(quiz_id,)).fetchall()
    correct = 0
    details = []
    for q in qs:
        selected = str(answers.get(str(q["id"]), ""))
        ok = selected.upper() == q["answer"].upper()
        correct += int(ok)
        details.append({"question_id":q["id"],"selected":selected,"correct":ok,
                        "answer":q["answer"],"explanation":q["explanation"]})
    cur = conn.execute("""INSERT INTO quiz_attempts(quiz_id,user_id,score,total)
                         VALUES(?,?,?,?)""",(quiz_id,user["id"],correct,len(qs)))
    attempt_id = cur.lastrowid
    for d in details:
        conn.execute("""INSERT INTO quiz_answers(attempt_id,question_id,selected,correct)
                        VALUES(?,?,?,?)""",
                     (attempt_id,d["question_id"],d["selected"],int(d["correct"])))
    conn.commit()
    conn.close()
    pct = round(correct*100/len(qs),1) if qs else 0
    return jsonify({"score":correct,"total":len(qs),"percent":pct,"details":details,
                    "feedback": "Excellent work!" if pct>=80 else
                                "Good progress. Review the explanations and retry." if pct>=60
                                else "Keep learning. Focus on the identified concepts and try again."})

@app.post("/api/assistant")
@auth_required
def assistant(user):
    data = request.get_json(force=True)
    message = (data.get("message") or "").strip()
    if not message:
        return jsonify({"error":"Enter a question."}),400
    low = message.lower()
    if "skill gap" in low or "gap" in low:
        skills = get_skills_for_user(user["id"])
        gaps = analyze_gaps(skills)[:4]
        text = "Your highest-priority gaps are: " + ", ".join(
            f"{g['name']} ({g['score']:.0f}% vs {g['target']:.0f}% target)" for g in gaps
        ) + ". Start with the largest gap and complete one practical activity."
    elif "igot" in low:
        text = "The iGOT Karmayogi section shows relevant catalogue items and keeps the integration behind an adapter. Official authenticated endpoints can be connected when credentials are available."
    elif "quiz" in low or "mcq" in low:
        text = "Go to AI Quiz Studio, upload a TXT, Markdown, CSV or PDF learning material, and generate 3–10 MCQs from its readable content."
    elif "python" in low:
        text = "For statistical work, focus on pandas, data cleaning, descriptive statistics, visualization and reproducible notebooks."
    elif "sql" in low:
        text = "For SQL, practice SELECT, WHERE, GROUP BY, JOIN, aggregate functions and validation queries using realistic official-data tables."
    elif "official statistics" in low:
        text = "Official statistics should be accurate, relevant, timely and transparent. Learn the statistical production process, metadata and quality principles."
    else:
        text = "I can help with competency gaps, official statistics, Python, SQL, data quality, iGOT learning, personalized courses and AI-generated quizzes. Tell me what you want to improve."
    return jsonify({"reply":text})

if __name__ == "__main__":
    port = int(os.getenv("PORT","5000"))
    debug_mode = os.getenv("FLASK_DEBUG","0") == "1"
    app.run(host="0.0.0.0",port=port,debug=debug_mode)
