import secrets
from datetime import datetime, timedelta, timezone
from functools import wraps
from flask import request, jsonify
from db import get_conn

SESSION_DAYS = 7

def create_session(user_id):
    token = secrets.token_urlsafe(32)
    expires = datetime.now(timezone.utc) + timedelta(days=SESSION_DAYS)
    conn = get_conn()
    conn.execute("INSERT INTO sessions(token,user_id,expires_at) VALUES(?,?,?)",
                 (token, user_id, expires.isoformat()))
    conn.commit()
    conn.close()
    return token

def get_user_from_token(token):
    if not token:
        return None
    conn = get_conn()
    row = conn.execute("""
        SELECT u.* FROM sessions s
        JOIN users u ON u.id=s.user_id
        WHERE s.token=? AND s.expires_at>?
    """, (token, datetime.now(timezone.utc).isoformat())).fetchone()
    conn.close()
    return dict(row) if row else None

def bearer_user():
    header = request.headers.get("Authorization", "")
    token = header.replace("Bearer ", "", 1).strip() if header.startswith("Bearer ") else ""
    return get_user_from_token(token)

def auth_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        user = bearer_user()
        if not user:
            return jsonify({"error": "Authentication required"}), 401
        return fn(user, *args, **kwargs)
    return wrapper

def logout(token):
    if token:
        conn = get_conn()
        conn.execute("DELETE FROM sessions WHERE token=?", (token,))
        conn.commit()
        conn.close()
