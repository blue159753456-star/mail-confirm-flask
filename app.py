from flask import Flask, request, jsonify
from datetime import datetime
from zoneinfo import ZoneInfo
import psycopg2
import os

app = Flask(__name__)

def get_conn():
    return psycopg2.connect(os.environ["DATABASE_URL"])

@app.route("/")
def home():
    return "Render Flask + DB 成功"

@app.route("/reset_db")
def reset_db():
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("DROP TABLE IF EXISTS confirm_logs")
    cur.execute("""
        CREATE TABLE confirm_logs (
            id SERIAL PRIMARY KEY,
            token TEXT UNIQUE,
            confirm_time TIMESTAMPTZ
        )
    """)

    conn.commit()
    cur.close()
    conn.close()

    return "confirm_logs 已重建完成"

@app.route("/confirm")
def confirm():
    token = request.args.get("token", "").strip()

    if not token:
        return "缺少 token", 400

    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS confirm_logs (
            id SERIAL PRIMARY KEY,
            token TEXT UNIQUE,
            confirm_time TIMESTAMPTZ
        )
    """)

    cur.execute("""
        INSERT INTO confirm_logs (token, confirm_time)
        VALUES (%s, %s)
        ON CONFLICT (token) DO NOTHING
    """, (token, datetime.utcnow()))

    conn.commit()

    if cur.rowcount == 0:
        cur.close()
        conn.close()
        return f"此連結已確認過（token={token}）"

    cur.close()
    conn.close()
    return f"確認成功 token={token}"

@app.route("/logs")
def logs():
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
        SELECT token, confirm_time AT TIME ZONE 'Asia/Taipei'
        FROM confirm_logs
        ORDER BY confirm_time DESC
    """)

    rows = cur.fetchall()

    cur.close()
    conn.close()

    result = ""
    for token, confirm_time in rows:
        result += f"{confirm_time}, token={token}\n"

    return f"<pre>{result}</pre>"
    from flask import jsonify

@app.route("/api/confirmed_tokens")
def api_confirmed_tokens():
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
        SELECT token, confirm_time AT TIME ZONE 'Asia/Taipei'
        FROM confirm_logs
        ORDER BY confirm_time DESC
    """)

    rows = cur.fetchall()

    cur.close()
    conn.close()

    data = []
    for token, confirm_time in rows:
        data.append({
            "token": token,
            "confirm_time": str(confirm_time)
        })

    return jsonify(data)
