import os
from flask import Flask, request, jsonify, render_template_string, url_for
import psycopg2
from psycopg2.extras import RealDictCursor

app = Flask(__name__)


# =========================
# DB
# =========================
def get_conn():
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        raise RuntimeError("找不到 DATABASE_URL")
    return psycopg2.connect(database_url)


def init_db():
    conn = None
    cur = None
    try:
        conn = get_conn()
        cur = conn.cursor()

        cur.execute("""
            CREATE TABLE IF NOT EXISTS confirm_tokens (
                id SERIAL PRIMARY KEY,
                token TEXT UNIQUE NOT NULL,
                status TEXT NOT NULL DEFAULT 'PENDING',
                created_time TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                confirm_time TIMESTAMPTZ,
                processed BOOLEAN NOT NULL DEFAULT FALSE
            )
        """)

        conn.commit()

    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()


# =========================
# UI（網銀等級）
# =========================
PAGE_TEMPLATE = """
<!doctype html>
<html lang="zh-Hant">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{{ title }}</title>

<style>
body {
    margin: 0;
    background: #f4f6f9;
    font-family: "Microsoft JhengHei", Arial;
}

/* 🔴 上方銀行紅條 */
.header-bar {
    background: #c40018;
    color: white;
    padding: 14px 20px;
    display: flex;
    align-items: center;
    justify-content: center;
}

.header-inner {
    width: 100%;
    max-width: 900px;
    display: flex;
    align-items: center;
}

/* LOGO */
.logo {
    height: 40px;
    margin-right: 12px;
}

/* 標題 */
.bank-title {
    font-size: 18px;
    font-weight: bold;
}

/* 主體 */
.wrap {
    display: flex;
    justify-content: center;
    padding: 40px 16px;
}

.card {
    width: 100%;
    max-width: 480px;
    background: white;
    border-radius: 14px;
    padding: 36px 28px;
    box-shadow: 0 20px 60px rgba(0,0,0,0.08);
    text-align: center;
}

/* icon */
.icon {
    font-size: 70px;
    margin-bottom: 16px;
}

.success { color: #22c55e; }
.error { color: #ef4444; }
.info { color: #3b82f6; }

/* 標題 */
.title {
    font-size: 22px;
    font-weight: bold;
    margin-bottom: 10px;
}

/* 內容 */
.message {
    font-size: 16px;
    color: #333;
    margin-bottom: 10px;
}

.note {
    font-size: 14px;
    color: #666;
    margin-top: 10px;
}

/* 分隔 */
.divider {
    margin: 24px 0;
    height: 1px;
    background: #eee;
}

/* footer */
.footer {
    font-size: 13px;
    color: #999;
}
</style>
</head>

<body>

<!-- 🔴 銀行標頭 -->
<div class="header-bar">
    <div class="header-inner">

        <!-- 有上傳 logo 才會顯示 -->
        <img src="{{ url_for('static', filename='logo.png') }}" class="logo"
             onerror="this.style.display='none'">

        <div class="bank-title">
            花蓮信用合作社
        </div>
    </div>
</div>

<div class="wrap">
    <div class="card">

        <div class="icon {{ theme }}">
            {% if theme == 'success' %}✔{% elif theme == 'error' %}✖{% else %}ℹ{% endif %}
        </div>

        <div class="title">{{ title }}</div>
        <div class="message">{{ message }}</div>

        {% if note %}
        <div class="note">{{ note }}</div>
        {% endif %}

        <div class="divider"></div>

        <div class="footer">
            The First Credit Cooperative Of Hualien
        </div>

    </div>
</div>

</body>
</html>
"""


def render_page(title, message, theme="info", note="", code=200):
    return render_template_string(
        PAGE_TEMPLATE,
        title=title,
        message=message,
        theme=theme,
        note=note
    ), code


# =========================
# Routes
# =========================
@app.route("/")
def index():
    return render_page("系統正常", "Mail 驗證服務運作中", "info")


@app.route("/confirm")
def confirm():
    token = request.args.get("token", "").strip()

    if not token:
        return render_page(
            "驗證失敗",
            "缺少驗證參數",
            "error",
            "請確認您是否使用完整連結",
            400
        )

    conn = None
    cur = None

    try:
        conn = get_conn()
        cur = conn.cursor()

        cur.execute("""
            SELECT status, created_time
            FROM confirm_tokens
            WHERE token = %s
        """, (token,))
        row = cur.fetchone()

        if not row:
            return render_page(
                "連結已失效",
                "此連結已失效或已更新",
                "error",
                "請使用最新驗證信件",
                400
            )

        status, created_time = row

        if status == "CONFIRMED":
            return render_page(
                "已完成確認",
                "此連結已使用過",
                "info",
                "無需重複操作"
            )

        cur.execute("""
            SELECT NOW() > (%s + INTERVAL '24 hours')
        """, (created_time,))
        expired = cur.fetchone()[0]

        if expired:
            return render_page(
                "連結已過期",
                "此驗證連結已過期",
                "error",
                "請重新申請驗證",
                400
            )

        cur.execute("""
            UPDATE confirm_tokens
            SET status = 'CONFIRMED',
                confirm_time = NOW()
            WHERE token = %s
        """, (token,))

        conn.commit()

        return render_page(
            "驗證成功",
            "您已完成電子郵件確認",
            "success",
            "系統已記錄您的驗證結果"
        )

    except Exception as e:
        if conn:
            conn.rollback()

        return render_page(
            "系統錯誤",
            "處理過程發生錯誤",
            "error",
            str(e),
            500
        )

    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()


# =========================
# API
# =========================
@app.route("/api/upload_tokens", methods=["POST"])
def upload_tokens():
    data = request.json or {}
    tokens = data.get("tokens", [])

    if not tokens:
        return jsonify({"error": "no tokens"}), 400

    conn = get_conn()
    cur = conn.cursor()

    try:
        cur.execute("DELETE FROM confirm_tokens")

        for t in tokens:
            cur.execute("""
                INSERT INTO confirm_tokens (token, status, created_time)
                VALUES (%s, 'PENDING', NOW())
            """, (t,))

        conn.commit()

        return jsonify({"message": "ok", "count": len(tokens)})

    finally:
        cur.close()
        conn.close()


@app.route("/api/new_tokens")
def new_tokens():
    conn = get_conn()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    cur.execute("""
        SELECT token, confirm_time
        FROM confirm_tokens
        WHERE status='CONFIRMED'
          AND processed = FALSE
        ORDER BY confirm_time
    """)

    rows = cur.fetchall()

    cur.close()
    conn.close()

    return jsonify(rows)


@app.route("/api/mark_processed", methods=["POST"])
def mark_processed():
    data = request.json or {}
    tokens = data.get("tokens", [])

    if not tokens:
        return jsonify({"error": "no tokens"}), 400

    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
        UPDATE confirm_tokens
        SET processed = TRUE
        WHERE token = ANY(%s)
    """, (tokens,))

    conn.commit()

    cur.close()
    conn.close()

    return jsonify({"updated": len(tokens)})


# =========================
init_db()

if __name__ == "__main__":
    app.run()
