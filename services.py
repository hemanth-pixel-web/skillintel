from db import get_conn
from ai_engine import analyze_gaps, recommendation_reason

def get_skills_for_user(user_id):
    conn = get_conn()
    rows = conn.execute("""
        SELECT s.id,s.name,s.category,s.description,
               COALESCE(us.score,0) score, COALESCE(us.target,80) target
        FROM skills s
        LEFT JOIN user_skills us ON us.skill_id=s.id AND us.user_id=?
        ORDER BY s.id
    """, (user_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_recommendations(user_id):
    skills = get_skills_for_user(user_id)
    gaps = analyze_gaps(skills)
    conn = get_conn()
    out = []
    for g in gaps[:5]:
        courses = conn.execute("""
            SELECT * FROM courses
            WHERE skill=?
            ORDER BY CASE WHEN source='iGOT' THEN 0 ELSE 1 END, id
            LIMIT 2
        """, (g["name"],)).fetchall()
        for c in courses:
            out.append({
                "skill": g["name"],
                "gap": g["gap"],
                "reason": recommendation_reason(g["name"], g["score"]),
                "course": dict(c)
            })
    conn.close()
    return out

def dashboard(user_id):
    conn = get_conn()
    user = conn.execute("SELECT id,name,email,role,department,designation FROM users WHERE id=?", (user_id,)).fetchone()
    skills = get_skills_for_user(user_id)
    progress = conn.execute("""
        SELECT p.percent,c.title,c.skill,c.duration,c.provider,c.url
        FROM progress p JOIN courses c ON c.id=p.course_id
        WHERE p.user_id=? ORDER BY p.updated_at DESC
    """, (user_id,)).fetchall()
    quiz_stats = conn.execute("""
        SELECT COUNT(*) attempts, COALESCE(AVG(CASE WHEN total>0 THEN score*100.0/total END),0) avg_score
        FROM quiz_attempts WHERE user_id=?
    """, (user_id,)).fetchone()
    assess = conn.execute("""
        SELECT score,total,created_at FROM assessments
        WHERE user_id=? ORDER BY id DESC LIMIT 1
    """, (user_id,)).fetchone()
    conn.close()

    avg_skill = round(sum(x["score"] for x in skills)/len(skills), 1) if skills else 0
    return {
        "user": dict(user),
        "skills": skills,
        "gaps": analyze_gaps(skills),
        "recommendations": get_recommendations(user_id),
        "progress": [dict(x) for x in progress],
        "stats": {
            "skill_score": avg_skill,
            "courses_active": len(progress),
            "quiz_attempts": quiz_stats["attempts"],
            "quiz_average": round(quiz_stats["avg_score"] or 0, 1),
            "assessment_score": round(assess["score"],1) if assess else None
        }
    }

def igot_courses():
    conn = get_conn()
    rows = conn.execute("SELECT * FROM courses WHERE source='iGOT' ORDER BY id").fetchall()
    conn.close()
    return [dict(r) for r in rows]
