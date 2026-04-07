from flask import Flask, request
from datetime import datetime
import psycopg2
import os

app = Flask(__name__)

def get_conn():
    return psycopg2.connect(os.environ["DATABASE_URL"])

@app.route("/")
def home():
    return "Render Flask + DB 成功"

@app.route("/confirm")
def confirm():
    token = request.args.get("token", "").strip()

    if not token:
        return "缺少 token", 400

    conn = get_conn()
    cur = conn.cursor()

    # 建表（第一次會自動建立）
    cur.execute("""
        CREATE TABLE IF NOT EXISTS confirm_logs (
            id SERIAL PRIMARY KEY,
            token TEXT,
            confirm_time TIMESTAMP
        )
    """)

    # 寫入資料
    cur.execute("""
        INSERT INTO confirm_logs (token, confirm_time)
        VALUES (%s, %s)
    """, (token, datetime.now()))

    conn.commit()
    cur.close()
    conn.close()

    return f"確認成功 token={token}"

@app.route("/logs")
def logs():
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
        SELECT token, confirm_time
        FROM confirm_logs
        ORDER BY confirm_time DESC
    """)

    rows = cur.fetchall()

    cur.close()
    conn.close()

    result = ""
    for r in rows:
        result += f"{r[1]}, token={r[0]}\n"

    return f"<pre>{result}</pre>"
