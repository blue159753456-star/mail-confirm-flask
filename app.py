from flask import Flask, request, jsonify
import psycopg2
import os
import uuid

app = Flask(__name__)


def get_conn():
    return psycopg2.connect(os.environ["DATABASE_URL"])


def format_dt(dt_value):
    if dt_value is None:
        return ""
    if hasattr(dt_value, "strftime"):
        return dt_value.strftime("%Y-%m-%d %H:%M:%S")
    return str(dt_value).split(".")[0]


@app.route("/")
def home():
    return "MAIL CONFIRM SYSTEM OK"


# 初始化資料表（只建一次後可不用再打）
@app.route("/init_db")
def init_db():
    conn = None
    cur = None
    try:
        conn = get_conn()
        cur = conn.cursor()

        cur.execute("""
            CREATE TABLE IF NOT EXISTS confirm_tokens (
                token TEXT PRIMARY KEY,
                email TEXT,
                status TEXT NOT NULL DEFAULT 'PENDING',
                created_time TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                confirm_time TIMESTAMPTZ,
                processed BOOLEAN NOT NULL DEFAULT FALSE
            )
        """)

        conn.commit()
        return "confirm_tokens 建立完成"

    except Exception as e:
        if conn:
            conn.rollback()
        return f"init_db 發生錯誤：{e}", 500

    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()


# 測試用：手動新增一筆 token
# 正式環境之後可拿掉
@app.route("/create_test_token")
def create_test_token():
    email = request.args.get("email", "").strip()
    token = uuid.uuid4().hex

    conn = None
    cur = None
    try:
        conn = get_conn()
        cur = conn.cursor()

        cur.execute("""
            INSERT INTO confirm_tokens (token, email, status)
            VALUES (%s, %s, 'PENDING')
        """, (token, email or None))

        conn.commit()

        return jsonify({
            "ok": True,
            "token": token,
            "email": email
        })

    except Exception as e:
        if conn:
            conn.rollback()
        return jsonify({"ok": False, "error": str(e)}), 500

    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()


# 客戶點確認連結
@app.route("/confirm")
def confirm():
    token = request.args.get("token", "").strip()

    if not token or len(token) > 200:
        return "此連結無效", 400

    conn = None
    cur = None
    try:
        conn = get_conn()
        cur = conn.cursor()

        cur.execute("""
            SELECT status
            FROM confirm_tokens
            WHERE token = %s
        """, (token,))

        row = cur.fetchone()

        if not row:
            return "此連結無效或不存在", 400

        status = row[0]

        if status == "CONFIRMED":
            return "此連結已確認過"

        cur.execute("""
            UPDATE confirm_tokens
            SET status = 'CONFIRMED',
                confirm_time = NOW()
            WHERE token = %s
        """, (token,))

        conn.commit()
        return "您已完成電子郵件確認"

    except Exception as e:
        if conn:
            conn.rollback()
        return f"系統錯誤：{e}", 500

    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()


# 查詢尚未處理的已確認資料
@app.route("/api/new_tokens")
def api_new_tokens():
    conn = None
    cur = None
    try:
        conn = get_conn()
        cur = conn.cursor()

        cur.execute("""
            SELECT token,
                   email,
                   confirm_time AT TIME ZONE 'Asia/Taipei'
            FROM confirm_tokens
            WHERE status = 'CONFIRMED'
              AND processed = FALSE
            ORDER BY confirm_time
        """)

        rows = cur.fetchall()

        data = []
        for token, email, confirm_time in rows:
            data.append({
                "token": token,
                "email": email or "",
                "confirm_time": format_dt(confirm_time)
            })

        return jsonify(data)

    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()


# 本機處理完成後，回寫已處理
@app.route("/api/mark_processed", methods=["POST"])
def api_mark_processed():
    conn = None
    cur = None
    try:
        data = request.get_json(silent=True) or {}
        tokens = data.get("tokens", [])

        if not tokens:
            return jsonify({"ok": False, "error": "缺少 tokens"}), 400

        conn = get_conn()
        cur = conn.cursor()

        cur.execute("""
            UPDATE confirm_tokens
            SET processed = TRUE
            WHERE token = ANY(%s)
        """, (tokens,))

        updated = cur.rowcount
        conn.commit()

        return jsonify({"ok": True, "updated": updated})

    except Exception as e:
        if conn:
            conn.rollback()
        return jsonify({"ok": False, "error": str(e)}), 500

    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()

@app.route("/api/create_token", methods=["POST"])
def api_create_token():
    conn = None
    cur = None
    try:
        data = request.get_json(silent=True) or {}
        email = str(data.get("email", "")).strip()

        if not email:
            return jsonify({"ok": False, "error": "缺少 email"}), 400

        import uuid
        token = uuid.uuid4().hex
        confirm_url = f"https://mail-confirm-flask.onrender.com/confirm?token={token}"

        conn = get_conn()
        cur = conn.cursor()

        cur.execute("""
            INSERT INTO confirm_tokens (token, email, status)
            VALUES (%s, %s, 'PENDING')
        """, (token, email))

        conn.commit()

        return jsonify({
            "ok": True,
            "email": email,
            "token": token,
            "confirm_url": confirm_url
        })

    except Exception as e:
        if conn:
            conn.rollback()
        return jsonify({"ok": False, "error": str(e)}), 500

    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()
